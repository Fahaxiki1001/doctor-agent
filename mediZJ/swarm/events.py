"""
事件系统：Agent 之间的异步通信机制
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid


class EventType(Enum):
    """事件类型枚举"""
    TASK_DECOMPOSED = "task_decomposed"          # LeadAgent 分解了任务
    SUBTASK_STARTED = "subtask_started"          # Agent 开始执行子任务
    SUBTASK_COMPLETED = "subtask_completed"      # Agent 完成子任务
    CONTEXT_UPDATED = "context_updated"          # 共享上下文更新
    AGENT_QUESTION = "agent_question"            # Agent 提出问题
    AGENT_ANSWER = "agent_answer"                # Agent 回答问题
    SWARM_STARTED = "swarm_started"              # Swarm 开始处理
    SWARM_COMPLETED = "swarm_completed"          # Swarm 完成处理
    AGENT_THINKING = "agent_thinking"            # Agent 推理思考内容
    AGENT_TOOL_STEP = "agent_tool_step"          # Agent 工具调用步骤
    AGENT_THINKING_DONE = "agent_thinking_done"  # Agent 推理轮次结束（含耗时）
    AGENT_CONTENT_DELTA = "agent_content_delta"  # Agent 最终回答 token 流式输出
    AGENT_QUESTIONNAIRE = "agent_questionnaire"  # Agent 向前端发送结构化问卷
    AGENT_QUESTIONNAIRE_CANCELLED = "agent_questionnaire_cancelled"  # 问卷被取消（超时/系统取消）
    TRACE_SPAN = "trace_span"                    # Trace span 完成事件（实时推送）
    INTENT_CLASSIFIED = "intent_classified"      # 意图识别结果（检索门控）
    HEALTH_TASK_STARTED = "task_started"
    HEALTH_RISK_UPDATED = "risk_update"
    HEALTH_SAFETY_WARNING = "safety_warning"
    HEALTH_WAITING_CONFIRMATION = "waiting_confirmation"
    HEALTH_TASK_COMPLETED = "task_completed"


@dataclass
class Event:
    """
    事件数据类

    Agent 通过发布事件到 SharedContext 来通信，
    而不是直接调用其他 Agent
    """
    type: EventType
    source_agent: str
    data: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    target_agents: Optional[List[str]] = None  # None 表示广播给所有 Agent

    def is_for_agent(self, agent_id: str) -> bool:
        """判断事件是否针对特定 Agent"""
        if self.target_agents is None:
            return True  # 广播事件
        return agent_id in self.target_agents

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        # Task events may enter traces and browser streams. Never serialize report
        # bodies or image payloads through this generic event channel.
        sensitive_keys = {
            "image_base64", "base64", "raw_report", "report_text",
            "original_report", "image_bytes",
        }
        safe_data = {
            key: value for key, value in self.data.items()
            if key not in sensitive_keys
        }
        return {
            "id": self.id,
            "type": self.type.value,
            "source_agent": self.source_agent,
            "timestamp": self.timestamp.isoformat(),
            "target_agents": self.target_agents,
            "data": safe_data
        }


def health_task_event(
    event_type: EventType,
    task_id: str,
    task_type: str,
    data: Optional[Dict[str, Any]] = None,
    source_agent: str = "health_task_runtime",
) -> Event:
    """Build a task event with the mandatory correlation fields."""

    allowed = {
        EventType.HEALTH_TASK_STARTED,
        EventType.HEALTH_RISK_UPDATED,
        EventType.HEALTH_SAFETY_WARNING,
        EventType.HEALTH_WAITING_CONFIRMATION,
        EventType.HEALTH_TASK_COMPLETED,
    }
    if event_type not in allowed:
        raise ValueError("event_type is not a health-task event")
    payload = {**(data or {}), "task_id": task_id, "task_type": task_type}
    return Event(type=event_type, source_agent=source_agent, data=payload)
