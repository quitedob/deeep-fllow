

import base64  # Base64编码解码
import json  # JSON处理
import logging  # 日志模块
import os  # 操作系统交互
from typing import Annotated, List, cast, Optional, Dict, Any  # 类型注解
from uuid import uuid4  # UUID生成

from fastapi import FastAPI, HTTPException, Query, Body  # FastAPI框架及组件
from fastapi.middleware.cors import CORSMiddleware  # CORS中间件
from fastapi.responses import Response, StreamingResponse  # FastAPI响应类型
from langchain_core.messages import AIMessageChunk, ToolMessage, BaseMessage  # Langchain消息类型
from langgraph.types import Command  # Langgraph命令类型

from src.config.tools import SELECTED_RAG_PROVIDER  # RAG提供者配置
from src.graph.builder import build_graph_with_memory  # 构建带记忆的图
from src.podcast.graph.builder import build_graph as build_podcast_graph  # 构建播客图
from src.ppt.graph.builder import build_graph as build_ppt_graph  # 构建PPT图
from src.prose.graph.builder import build_graph as build_prose_graph  # 构建文章图
from src.rag.builder import build_retriever  # 构建RAG检索器
from src.rag.retriever import Resource  # RAG资源模型
from src.server.chat_request import (  # 聊天请求相关模型
    ChatMessage,
    ChatRequest,
    GeneratePodcastRequest,
    GeneratePPTRequest,
    GenerateProseRequest,
    TTSRequest,
)
from src.server.mcp_request import MCPServerMetadataRequest, MCPServerMetadataResponse  # MCP请求相关模型
from src.server.mcp_utils import load_mcp_tools  # MCP工具加载函数
from src.server.rag_request import (  # RAG请求相关模型
    RAGConfigResponse,
    RAGResourceRequest,
    RAGResourcesResponse,
)
from src.tools import VolcengineTTS  # 火山TTS工具
from src.utils.logging import init_logger  # 日志初始化工具
from src.config.loader import load_yaml_config  # YAML配置加载

# 初始化日志记录器
init_logger()  # 默认级别，通常为INFO

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器

# FastAPI 应用实例
app = FastAPI(
    title="DeerFlow API",  # API标题
    description="DeerFlow 智能研究助手 API 服务",  # API描述
    version="0.1.0",  # API版本
)

# 添加CORS中间件，允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源访问
    allow_credentials=True,  # 允许携带凭证
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)

# 构建带记忆功能的LangGraph图实例
# 简化注释：构建主图
graph = build_graph_with_memory()

# 全局变量，用于存储最近一次API调用的 LangGraph 流程的最终状态
# 简化注释：全局最新计划信息
latest_api_plan_info: Optional[Dict[str, Any]] = None


# --- API 端点定义 ---

@app.post("/api/chat/stream", summary="流式聊天接口")  # API端点：流式聊天
async def chat_stream(request: ChatRequest):
    """
    处理流式聊天请求，与LangGraph工作流交互并以SSE（Server-Sent Events）形式返回结果。
    简化注释：流式聊天处理
    """
    thread_id = request.thread_id  # 获取线程ID
    if thread_id == "__default__":  # 如果是默认线程ID
        thread_id = str(uuid4())  # 生成新的UUID作为线程ID
    logger.info(f"流式聊天请求开始，线程ID: {thread_id}，用户消息数: {len(request.messages)}")  # 日志：请求开始

    # 异步生成器，用于LangGraph的流式输出
    # 简化注释：异步流生成器
    response_generator = _astream_workflow_generator(
        messages=request.messages,  # 历史消息
        thread_id=thread_id,  # 线程ID
        resources=request.resources,  # RAG资源
        max_plan_iterations=request.max_plan_iterations,  # 最大规划迭代次数
        max_step_num=request.max_step_num,  # 最大步骤数
        max_search_results=request.max_search_results,  # 最大搜索结果数
        auto_accepted_plan=request.auto_accepted_plan,  # 自动接受计划标志
        interrupt_feedback=request.interrupt_feedback,  # 中断反馈信息
        mcp_settings=request.mcp_settings,  # MCP设置
        enable_background_investigation=request.enable_background_investigation,  # 启用背景调查标志
    )
    return StreamingResponse(response_generator, media_type="text/event-stream")  # 返回流式响应


async def _astream_workflow_generator(  # 内部异步生成器函数
        messages: List[ChatMessage],  # 消息列表
        thread_id: str,  # 线程ID
        resources: List[Resource],  # RAG资源
        max_plan_iterations: int,  # 最大规划迭代次数
        max_step_num: int,  # 最大步骤数
        max_search_results: int,  # 最大搜索结果数
        auto_accepted_plan: bool,  # 自动接受计划标志
        interrupt_feedback: str,  # 中断反馈
        mcp_settings: dict,  # MCP设置
        enable_background_investigation: bool,  # 启用背景调查
):
    """
    LangGraph工作流的异步事件流生成器。
    简化注释：工作流事件生成
    """
    # 准备LangGraph的初始输入状态
    # 简化注释：准备初始状态
    initial_input_state = {
        "messages": [msg.model_dump() for msg in messages],  # 将Pydantic模型转为字典
        "plan_iterations": 0,  # 初始化规划迭代次数
        "final_report": "",  # 初始化最终报告
        "current_plan": None,  # 初始化当前计划
        "observations": [],  # 初始化观察结果列表
        "auto_accepted_plan": auto_accepted_plan,  # 设置自动接受计划标志
        "enable_background_investigation": enable_background_investigation,  # 设置背景调查标志
    }

    # 如果不是自动接受计划且有中断反馈，则准备Command以恢复执行
    # 简化注释：处理中断反馈
    if not auto_accepted_plan and interrupt_feedback:
        resume_msg = f"[{interrupt_feedback}]"  # 构造恢复消息
        if messages and messages[-1].content:  # 如果有历史消息
            # 将最后一条用户消息内容附加到恢复消息中
            last_user_content = messages[-1].content
            if isinstance(last_user_content, str):
                resume_msg += f" {last_user_content}"
            elif isinstance(last_user_content, list) and last_user_content and last_user_content[0].type == "text":
                resume_msg += f" {last_user_content[0].text}"
        initial_input_state = Command(resume=resume_msg)  # 使用Command对象作为输入
        logger.info(f"从中断恢复，反馈: {resume_msg}")  # 日志：从中断恢复

    # 配置LangGraph执行参数
    # 简化注释：LangGraph配置
    execution_config = {
        "thread_id": thread_id,  # 线程ID
        "resources": resources,  # RAG资源
        "max_plan_iterations": max_plan_iterations,  # 最大规划迭代
        "max_step_num": max_step_num,  # 最大步骤数
        "max_search_results": max_search_results,  # 最大搜索结果
        "mcp_settings": mcp_settings,  # MCP设置
    }
    logger.debug(f"LangGraph 执行配置: {execution_config}")  # 日志：执行配置

    # 异步迭代LangGraph的事件流
    # 简化注释：迭代事件流
    async for agent_name_tuple, _, event_data in graph.astream(
            input=initial_input_state,  # 初始输入
            config=execution_config,  # 执行配置
            stream_mode=["messages", "updates"],  # 流模式：消息和更新
            subgraphs=True,  # 包括子图事件
    ):
        try:
            if isinstance(event_data, dict):  # 如果事件数据是字典
                if "__interrupt__" in event_data:  # 如果是中断事件
                    # 构造并发送中断事件到客户端
                    # 简化注释：处理中断事件
                    interrupt_content = event_data["__interrupt__"][0].value  # 获取中断内容
                    interrupt_id = event_data["__interrupt__"][0].ns[0] if event_data["__interrupt__"][
                        0].ns else "unknown_interrupt"  # 获取中断ID
                    logger.info(f"工作流中断: ID={interrupt_id}, 内容='{interrupt_content[:100]}...'")  # 日志：工作流中断
                    yield _make_event(
                        "interrupt",  # 事件类型：中断
                        {
                            "thread_id": thread_id,  # 线程ID
                            "id": interrupt_id,  # 中断ID
                            "role": "assistant",  # 角色：助手
                            "content": interrupt_content,  # 中断内容
                            "finish_reason": "interrupt",  # 完成原因：中断
                            "options": [  # 用户可选操作
                                {"text": "编辑计划", "value": "edit_plan"},  # 编辑计划
                                {"text": "开始研究", "value": "accepted"},  # 接受计划并开始
                            ],
                        },
                    )
                # 在这里可以添加对其他特定字典类型事件的处理逻辑
                # 例如，如果 'updates' 流模式下有其他类型的状态更新，可以在此处理
                # elif "some_other_key" in event_data:
                #     logger.debug(f"收到状态更新: {event_data}")
                #     # 根据需要选择是否以及如何将这些更新发送到客户端
                continue  # 处理完字典类型事件后继续下一个事件

            # 处理Langchain消息类型的事件
            # 简化注释：处理Langchain消息
            message_chunk, _ = cast(  # 类型转换
                tuple[BaseMessage, dict[str, any]], event_data  # 事件数据包含消息块和元数据
            )
            agent_name = agent_name_tuple[0].split(":")[0] if agent_name_tuple else "unknown_agent"  # 获取Agent名称

            # 构造SSE事件消息体
            # 简化注释：构造SSE事件
            event_stream_message: dict[str, any] = {
                "thread_id": thread_id,  # 线程ID
                "agent": agent_name,  # Agent名称
                "id": getattr(message_chunk, 'id', str(uuid4())),  # 消息ID
                "role": "assistant",  # 角色：助手
                "content": getattr(message_chunk, 'content', ""),  # 消息内容
            }

            # 如果消息元数据中有完成原因，则添加到事件中
            # 简化注释：添加完成原因
            if hasattr(message_chunk, 'response_metadata') and message_chunk.response_metadata.get("finish_reason"):
                event_stream_message["finish_reason"] = message_chunk.response_metadata.get("finish_reason")

            # 根据消息类型确定事件类型并发送
            # 简化注释：区分消息类型发送
            if isinstance(message_chunk, ToolMessage):  # 如果是工具消息
                event_stream_message["tool_call_id"] = message_chunk.tool_call_id  # 工具调用ID
                logger.debug(f"工具调用结果事件: {event_stream_message}")  # 日志：工具结果
                yield _make_event("tool_call_result", event_stream_message)  # 发送工具调用结果事件
            elif isinstance(message_chunk, AIMessageChunk):  # 如果是AI消息块
                if getattr(message_chunk, 'tool_calls', None):  # 如果包含完整工具调用
                    event_stream_message["tool_calls"] = message_chunk.tool_calls  # 工具调用信息
                    if getattr(message_chunk, 'tool_call_chunks', None):  # 如果同时有工具调用块
                        event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks  # 工具调用块信息
                    logger.debug(f"工具调用事件: {event_stream_message}")  # 日志：工具调用
                    yield _make_event("tool_calls", event_stream_message)  # 发送工具调用事件
                elif getattr(message_chunk, 'tool_call_chunks', None):  # 如果只包含工具调用块
                    event_stream_message["tool_call_chunks"] = message_chunk.tool_call_chunks  # 工具调用块信息
                    logger.debug(f"工具调用块事件: {event_stream_message}")  # 日志：工具调用块
                    yield _make_event("tool_call_chunks", event_stream_message)  # 发送工具调用块事件
                else:  # 如果是普通AI消息块
                    logger.debug(f"消息块事件: {event_stream_message.get('content')[:100]}...")  # 日志：消息块内容
                    yield _make_event("message_chunk", event_stream_message)  # 发送消息块事件
            else:  # 其他类型的消息（不常见于此流模式，但作为备用处理）
                logger.warning(f"未处理的事件数据类型: {type(event_data)}, 内容: {str(event_data)[:200]}")  # 日志：未处理类型
        except Exception as e:
            logger.error(f"处理流事件时发生错误: {e}", exc_info=True)  # 日志：事件处理错误
            # 可以选择向客户端发送一个错误事件
            yield _make_event("error", {"message": f"处理事件时出错: {str(e)}", "thread_id": thread_id})

    logger.info(f"流式聊天请求完成，线程ID: {thread_id}")  # 日志：请求完成


def _make_event(event_type: str, data: dict[str, any]) -> str:  # 内部函数：构造SSE事件字符串
    """
    将事件数据格式化为SSE（Server-Sent Events）字符串。
    简化注释：格式化SSE事件
    """
    if data.get("content") == "":  # 如果内容为空字符串
        data.pop("content")  # 移除内容字段以减少传输数据量
    json_data = json.dumps(data, ensure_ascii=False)  # 将数据转为JSON字符串，确保非ASCII字符正确编码
    return f"event: {event_type}\ndata: {json_data}\n\n"  # 返回SSE格式的字符串


@app.post("/api/tts", summary="文本转语音接口")  # API端点：文本转语音
async def text_to_speech_api(request: TTSRequest):  # 注意函数名修改以符合PEP8，FastAPI通过装饰器路径映射
    """
    接收文本并使用火山引擎TTS API将其转换为语音。
    简化注释：文本转语音处理
    """
    logger.info(f"TTS请求：文本='{request.text[:50]}...'，语音类型='{request.voice_type}'")  # 日志：TTS请求
    try:
        # 从环境变量获取火山TTS配置，简化注释：获取TTS配置
        app_id = os.getenv("VOLCENGINE_TTS_APPID")
        access_token = os.getenv("VOLCENGINE_TTS_ACCESS_TOKEN")
        if not app_id or not access_token:  # 检查配置是否存在
            logger.error("火山TTS配置缺失：VOLCENGINE_TTS_APPID 或 VOLCENGINE_TTS_ACCESS_TOKEN 未设置。")  # 日志：配置缺失
            raise HTTPException(
                status_code=500, detail="TTS服务配置不完整，无法处理请求。"
            )
        cluster = os.getenv("VOLCENGINE_TTS_CLUSTER", "volcano_tts")  # TTS集群，默认为volcano_tts
        default_voice_type = os.getenv("VOLCENGINE_TTS_VOICE_TYPE", "BV700_V2_streaming")  # 默认语音类型

        # 实例化TTS客户端，简化注释：实例化TTS客户端
        tts_client = VolcengineTTS(
            appid=app_id,  # 应用ID
            access_token=access_token,  # 访问令牌
            cluster=cluster,  # 集群
            # 如果请求中指定了 voice_type，则使用它，否则使用环境变量或硬编码的默认值
            voice_type=request.voice_type or default_voice_type,  # 语音类型
        )
        # 调用TTS API进行转换，简化注释：调用TTS API
        result = tts_client.text_to_speech(
            text=request.text[:1024],  # 限制文本长度，防止超长请求
            encoding=request.encoding,  # 音频编码
            speed_ratio=request.speed_ratio,  # 语速
            volume_ratio=request.volume_ratio,  # 音量
            pitch_ratio=request.pitch_ratio,  # 音调
            text_type=request.text_type,  # 文本类型
            with_frontend=request.with_frontend,  # 是否使用前端处理
            frontend_type=request.frontend_type,  # 前端类型
        )

        if not result.get("success"):  # 如果转换失败
            error_detail = result.get("error", "未知TTS错误")  # 获取错误详情
            logger.error(f"TTS API调用失败：{error_detail}")  # 日志：API调用失败
            raise HTTPException(status_code=500, detail=f"TTS服务调用失败: {error_detail}")  # 抛出异常

        # 解码Base64音频数据，简化注释：解码音频数据
        audio_data_base64 = result.get("audio_data")
        if not audio_data_base64:
            logger.error("TTS API未返回音频数据。")  # 日志：无音频数据
            raise HTTPException(status_code=500, detail="TTS服务未返回音频数据")

        audio_data_bytes = base64.b64decode(audio_data_base64)  # Base64解码

        # 返回音频文件响应，简化注释：返回音频响应
        media_type = f"audio/{request.encoding}"  # 音频媒体类型
        filename = f"tts_output.{request.encoding}"  # 下载文件名
        logger.info(f"TTS成功，返回音频文件：{filename}, 大小: {len(audio_data_bytes)}字节")  # 日志：TTS成功
        return Response(
            content=audio_data_bytes,  # 音频内容
            media_type=media_type,  # 媒体类型
            headers={"Content-Disposition": f"attachment; filename={filename}"},  # 下载头
        )
    except HTTPException:  # 如果是HTTPException，直接重新抛出
        raise
    except Exception as e:  # 其他所有异常
        logger.exception(f"TTS接口发生意外错误: {e}")  # 日志：意外错误
        raise HTTPException(status_code=500, detail=f"处理TTS请求时发生意外错误: {str(e)}")  # 抛出500错误


@app.post("/api/podcast/generate", summary="生成播客音频")  # API端点：生成播客
async def generate_podcast_api(request: GeneratePodcastRequest):  # 注意函数名修改
    """
    根据输入内容（通常是研究报告的Markdown文本）生成播客音频。
    简化注释：生成播客处理
    """
    logger.info(f"播客生成请求：内容长度 {len(request.content)}")  # 日志：播客请求
    try:
        report_content = request.content  # 获取报告内容
        # 构建播客生成图（此图独立于主研究图）
        # 简化注释：构建播客图
        podcast_workflow = build_podcast_graph()
        # 调用播客图，输入为报告内容
        # 简化注释：调用播客图
        final_state = podcast_workflow.invoke({"input": report_content})
        audio_bytes = final_state.get("output")  # 获取最终的音频字节

        if not audio_bytes:  # 如果没有音频输出
            logger.error("播客生成流程未产生音频输出。")  # 日志：无音频输出
            raise HTTPException(status_code=500, detail="播客生成失败，未获取到音频数据。")

        logger.info(f"播客音频生成成功，大小: {len(audio_bytes)}字节")  # 日志：播客成功
        return Response(content=audio_bytes, media_type="audio/mp3")  # 返回MP3音频响应
    except Exception as e:  # 捕获所有异常
        logger.exception(f"生成播客过程中发生错误: {e}")  # 日志：播客生成错误
        raise HTTPException(status_code=500, detail=f"生成播客失败: {str(e)}")  # 抛出500错误


@app.post("/api/ppt/generate", summary="生成PPT演示文稿")  # API端点：生成PPT
async def generate_ppt_api(request: GeneratePPTRequest):  # 注意函数名修改
    """
    根据输入内容（通常是研究报告的Markdown文本）生成PPTX演示文稿。
    简化注释：生成PPT处理
    """
    logger.info(f"PPT生成请求：内容长度 {len(request.content)}")  # 日志：PPT请求
    try:
        report_content = request.content  # 获取报告内容
        # 构建PPT生成图（此图独立于主研究图）
        # 简化注释：构建PPT图
        ppt_workflow = build_ppt_graph()
        # 调用PPT图，输入为报告内容
        # 简化注释：调用PPT图
        final_state = ppt_workflow.invoke({"input": report_content})
        generated_file_path = final_state.get("generated_file_path")  # 获取生成的文件路径

        if not generated_file_path or not os.path.exists(generated_file_path):  # 如果路径无效或文件不存在
            logger.error(f"PPT生成流程未产生有效文件路径或文件不存在：{generated_file_path}")  # 日志：PPT路径无效
            raise HTTPException(status_code=500, detail="PPT生成失败，无法找到生成的演示文稿文件。")

        with open(generated_file_path, "rb") as f:  # 以二进制读取模式打开文件
            ppt_bytes = f.read()  # 读取文件字节

        # 清理临时生成的PPT文件
        # 简化注释：清理临时文件
        try:
            os.remove(generated_file_path)
            logger.info(f"已清理临时PPT文件: {generated_file_path}")
        except Exception as e_remove:
            logger.warning(f"清理临时PPT文件失败: {generated_file_path}, 错误: {e_remove}")

        logger.info(f"PPT生成成功，文件大小: {len(ppt_bytes)}字节")  # 日志：PPT成功
        return Response(  # 返回PPTX文件响应
            content=ppt_bytes,  # 文件内容
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",  # PPTX媒体类型
            headers={"Content-Disposition": "attachment; filename=generated_presentation.pptx"}  # 下载头
        )
    except Exception as e:  # 捕获所有异常
        logger.exception(f"生成PPT过程中发生错误: {e}")  # 日志：PPT生成错误
        raise HTTPException(status_code=500, detail=f"生成PPT失败: {str(e)}")  # 抛出500错误


@app.post("/api/prose/generate", summary="生成或修改文章段落")  # API端点：文章处理
async def generate_prose_api(request: GenerateProseRequest):  # 注意函数名修改
    """
    根据用户提供的文本、操作选项（如续写、改进等）和自定义指令，生成或修改文章段落。
    结果以流式方式返回。
    简化注释：文章处理接口
    """
    logger.info(
        f"文章处理请求：操作='{request.option}', 提示长度={len(request.prompt)}, 命令='{request.command}'")  # 日志：文章请求
    try:
        # 构建文章处理图（此图独立）
        # 简化注释：构建文章图
        prose_workflow = build_prose_graph()
        # 异步流式调用文章处理图
        # 简化注释：调用文章图
        events = prose_workflow.astream(
            {
                "content": request.prompt,  # 基础内容/提示
                "option": request.option,  # 操作选项
                "command": request.command,  # 自定义指令
            },
            stream_mode="messages",  # 流模式：消息
            subgraphs=True,  # 包括子图事件
        )

        # 将事件流转换为SSE格式的流式响应
        # 简化注释：流式响应转换
        async def event_stream():
            async for agent_name_tuple, event_list in events:  # 迭代事件
                if event_list and isinstance(event_list, list) and event_list[0]:
                    message_content = getattr(event_list[0], 'content', "")  # 获取消息内容
                    # agent_name = agent_name_tuple[0].split(":")[0] if agent_name_tuple else "prose_agent" # 获取Agent名
                    # logger.debug(f"文章处理流事件 from {agent_name}: {message_content[:100]}...") # 日志：流事件
                    yield _make_event("message_chunk", {"content": message_content})  # 发送消息块事件
            logger.info("文章处理流式响应完成。")  # 日志：流式完成

        return StreamingResponse(event_stream(), media_type="text/event-stream")  # 返回流式响应
    except Exception as e:  # 捕获所有异常
        logger.exception(f"文章处理过程中发生错误: {e}")  # 日志：文章处理错误
        raise HTTPException(status_code=500, detail=f"文章处理失败: {str(e)}")  # 抛出500错误


@app.post("/api/mcp/server/metadata", response_model=MCPServerMetadataResponse,
          summary="获取MCP服务器元数据")  # API端点：MCP元数据
async def mcp_server_metadata_api(request: MCPServerMetadataRequest):  # 注意函数名修改
    """
    获取指定MCP（多功能协作协议）服务器的元数据，包括其支持的工具列表。
    简化注释：MCP元数据接口
    """
    logger.info(
        f"MCP元数据请求: transport='{request.transport}', command='{request.command}', url='{request.url}'")  # 日志：MCP请求
    try:
        # 设置默认超时时间，对于首次执行的MCP服务器，可能需要更长时间来初始化
        # 简化注释：设置超时
        timeout = request.timeout_seconds if request.timeout_seconds is not None else 300  # 若请求中指定则使用，否则默认300秒

        # 调用工具函数加载MCP工具
        # 简化注释：加载MCP工具
        tools = await load_mcp_tools(
            server_type=request.transport,  # 服务器类型 (stdio 或 sse)
            command=request.command,  # stdio模式下的命令
            args=request.args,  # stdio模式下的参数
            url=request.url,  # sse模式下的URL
            env=request.env,  # 环境变量
            timeout_seconds=timeout,  # 超时时间
        )

        # 构造响应数据
        # 简化注释：构造MCP响应
        response = MCPServerMetadataResponse(
            transport=request.transport,  # 类型
            command=request.command,  # 命令
            args=request.args,  # 参数
            url=request.url,  # URL
            env=request.env,  # 环境变量
            tools=[tool.name for tool in tools] if tools else [],  # 工具名称列表
        )
        logger.info(f"MCP元数据响应：共发现 {len(response.tools)} 个工具。")  # 日志：MCP响应
        return response  # 返回响应
    except HTTPException:  # 如果是HTTPException，直接重新抛出
        raise
    except Exception as e:  # 其他所有异常
        logger.exception(f"获取MCP服务器元数据时发生错误: {e}")  # 日志：MCP错误
        raise HTTPException(status_code=500, detail=f"获取MCP元数据失败: {str(e)}")  # 抛出500错误


@app.get("/api/rag/config", response_model=RAGConfigResponse, summary="获取RAG配置")  # API端点：RAG配置
async def rag_config_api():  # 注意函数名修改
    """
    获取当前系统中RAG（检索增强生成）的配置信息，主要是RAG提供者的类型。
    简化注释：RAG配置接口
    """
    logger.info(f"RAG配置请求，当前提供者: {SELECTED_RAG_PROVIDER}")  # 日志：RAG配置请求
    return RAGConfigResponse(provider=SELECTED_RAG_PROVIDER)  # 返回RAG提供者信息


@app.get("/api/rag/resources", response_model=RAGResourcesResponse, summary="查询RAG资源")  # API端点：RAG资源
async def rag_resources_api(request: Annotated[RAGResourceRequest, Query()]):  # 注意函数名修改，使用Query进行GET参数绑定
    """
    根据查询条件列出RAG中可用的资源（如数据集、文档库等）。
    简化注释：RAG资源查询接口
    """
    query_str = request.query if request else None  # 获取查询字符串
    logger.info(f"RAG资源查询请求，查询词: '{query_str}'")  # 日志：RAG资源请求
    try:
        retriever = build_retriever()  # 构建RAG检索器实例
        if retriever:  # 如果检索器构建成功
            resources_list = retriever.list_resources(query_str)  # 列出资源
            logger.info(f"RAG资源查询成功，找到 {len(resources_list)} 个资源。")  # 日志：查询成功
            return RAGResourcesResponse(resources=resources_list)  # 返回资源列表
        else:  # 如果检索器未配置或构建失败
            logger.warning("RAG检索器未配置或初始化失败，返回空资源列表。")  # 日志：检索器失败
            return RAGResourcesResponse(resources=[])  # 返回空列表
    except Exception as e:  # 捕获所有异常
        logger.exception(f"查询RAG资源时发生错误: {e}")  # 日志：RAG资源错误
        raise HTTPException(status_code=500, detail=f"查询RAG资源失败: {str(e)}")  # 抛出500错误


# --- FastAPI 服务启动 (用于直接运行此文件进行开发) ---
if __name__ == "__main__":
    # 这部分主要用于开发时直接运行此脚本启动服务。
    # 生产部署时，通常使用 `uvicorn src.server.app:app --host 0.0.0.0 --port 8000` 命令。
    # 简化注释：服务器启动命令（开发用）
    logger.info("通过 `python src/server/app.py` 启动 FastAPI 开发服务器...")  # 日志：开发服务器启动
    uvicorn.run("src.server.app:app", host="0.0.0.0", port=8000, reload=True)  # 运行Uvicorn