# 文件路径: src/models/schemas.py
# 主要功能：定义项目所需的所有 Pydantic 模型，用于规范 LLM 的输出。
# 简化注释：定义 Pydantic 模型

from typing import List, Literal, Optional # Added Optional
from pydantic import BaseModel, Field

class CoordinatorOutput(BaseModel):
    """
    协调员节点期望解析的 JSON 结构。
    """
    # 简化注释：协调员输出模型
    need_background: bool = Field(..., description="是否需要外部背景信息")
    activated_agents: List[Literal["planner", "research_team", "reporter", "basic"]] = Field(
        ..., description="需要激活的智能体列表，例如: ['planner','research_team']"
    )
    routing_strategy: Literal["default"] = Field("default", description="路由策略，固定为 default")
    notes: str = Field(..., description="对路由决策的简要说明")


class PlannerStep(BaseModel):
    """
    规划师输出的单个任务步骤。
    """
    # 简化注释：规划师单步任务模型
    task: str = Field(..., description="任务描述")
    tools: List[str] = Field(..., description="任务对应的工具列表，例如 ['fused_search_tool']")
    description: str = Field(..., description="对任务的补充说明")


class PlannerOutput(BaseModel):
    """
    规划师节点期望解析的、包含多个步骤的计划。
    """
    # 简化注释：规划师完整计划模型
    plan: List[PlannerStep] = Field(..., description="分步规划列表")

class PPTSlide(BaseModel):
    """
    单张幻灯片的结构模型
    """
    slide_title: str = Field(..., description="幻灯片标题")
    bullet_points: List[str] = Field(..., description="要点列表")
    images: Optional[List[str]] = Field(None, description="可选的图片 URL 列表")
    notes: Optional[str] = Field(None, description="可选的演讲者备注")

class PPTOutputSchema(BaseModel):
    """
    完整的 PPT 输出结构，包含一个幻灯片列表
    """
    slides: List[PPTSlide] = Field(..., description="幻灯片列表")

class PodcastScriptOutput(BaseModel):
    """
    Podcast 脚本的结构模型
    """
    title: str = Field(..., description="播客节目标题")
    intro: str = Field(..., description="开场白和主持人介绍")
    segments: List[str] = Field(..., description="播客的主要内容片段列表")
    outro: str = Field(..., description="结束语和感谢词")

# 新增：意图识别节点的输出模型
class IntentOutput(BaseModel):
    """
    意图识别节点的输出模型。
    简化注释：意图识别输出
    """
    intent: Literal[
        "research", "clarification", "greeting", "chitchat", "rejection",
        "report_generation", "ppt_generation", "podcast_generation", "vision_analysis", "unknown"
    ] = Field(..., description="识别出的用户意图")
    confidence: Optional[float] = Field(None, description="意图识别的置信度 (0.0 to 1.0)", ge=0, le=1)
    details: Optional[str] = Field(None, description="关于意图的额外细节或参数")