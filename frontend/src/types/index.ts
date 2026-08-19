/** 前端类型定义 */

// ============================================================
// SSE 事件类型系统
// ============================================================

/** 所有 SSE 事件类型 */
export type SSEEventType =
  | 'start'
  | 'task_decomposed'
  | 'agent_start'
  | 'agent_tool_call'
  | 'agent_tool_result'
  | 'agent_complete'
  | 'agent_thinking'
  | 'agent_tool_step'
  | 'agent_thinking_done'
  | 'agent_content_delta'
  | 'agent_questionnaire'
  | 'agent_questionnaire_cancelled'
  | 'intent_classified'
  | 'trace_span'
  | 'task_started'
  | 'risk_update'
  | 'safety_warning'
  | 'waiting_confirmation'
  | 'task_completed'
  | 'suggestions'
  | 'done'
  | 'error'

/** SSE 原始消息结构 */
export interface SSEMessage {
  event: string
  data: Record<string, unknown>
}

// ---- 各事件的 data 类型 ----

export interface StartData {
  session_id: string
  trace_id?: string
}

export interface TaskDecomposedData {
  id?: string
  timestamp?: string
  data?: {
    subtask_id?: string
    type?: string
    description?: string
    assigned_agent?: string
  }
}

export interface AgentStartData {
  source_agent?: string
  agent_id?: string
  id?: string
  timestamp?: string
  data?: {
    subtask_id?: string
    subtask_type?: string
    tool_calls?: number
    mode?: string
    [key: string]: unknown
  }
}

export interface AgentCompleteData {
  source_agent?: string
  agent_id?: string
  id?: string
  timestamp?: string
  data?: {
    execution_time?: number
    subtasks_completed?: number
    [key: string]: unknown
  }
}

export interface AgentThinkingData {
  source_agent?: string
  id?: string
  timestamp?: string
  data?: {
    content: string
    iteration: number
    [key: string]: unknown
  }
}

export interface AgentToolStepData {
  source_agent?: string
  id?: string
  timestamp?: string
  data?: {
    tool_name: string
    arguments: Record<string, unknown>
    result: unknown
    success?: boolean
    iteration: number
  }
}

export interface AgentThinkingDoneData {
  source_agent?: string
  id?: string
  timestamp?: string
  data?: {
    iteration: number
    elapsed_seconds?: number
  }
}

export interface AgentContentDeltaData {
  data?: {
    token: string
    is_final?: boolean
  }
}

export interface AgentQuestionnaireData {
  questionnaire_id: string
  questionnaire_data?: {
    questions: QuestionnaireQuestion[]
  }
  data?: {
    questionnaire_id: string
    questionnaire_data?: {
      questions: QuestionnaireQuestion[]
    }
  }
}

export interface IntentClassifiedData {
  source_agent?: string
  id?: string
  timestamp?: string
  data?: {
    intent: 'medical' | 'others'
    confidence: number
    source: string
    reason?: string
    skip_long_term_retrieval?: boolean
  }
}

export interface DoneData {
  answer: string
  assistant_message_id?: string
  trace_id?: string
  citations?: Citation[]
  swarm_enabled?: boolean
  agents_involved?: string[]
  total_time?: number
  time_to_first_token?: number
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
  performance_metrics?: {
    parallel_efficiency?: number
    information_coverage?: number
    redundancy?: number
  }
}

export interface ErrorData {
  error: string
}

export interface HealthTaskEventData {
  task_id: string
  task_type: HealthTaskType
  status?: HealthTaskStatus
  risk_level?: RiskLevel
  safety_decision?: string
}

// ============================================================
// UI 模型
// ============================================================

export interface QuestionOption {
  label: string
  description?: string
}

export interface QuestionnaireQuestion {
  id?: string
  header: string
  type: 'enum' | 'multi' | 'input' | 'number'
  required: boolean
  text: string
  options: QuestionOption[]
}

export type HealthTaskType = 'triage' | 'knowledge_search' | 'report_interpretation'
export type HealthTaskStatus =
  | 'created'
  | 'collecting'
  | 'processing'
  | 'waiting_confirmation'
  | 'completed'
  | 'needs_medical_attention'
  | 'failed'
  | 'cancelled'

export interface HealthTask {
  task_id: string
  task_type: HealthTaskType
  session_id?: string | null
  status: HealthTaskStatus
  input_snapshot: Record<string, unknown>
  result: Record<string, unknown>
  safety_flags: Array<Record<string, unknown>>
  trace_id?: string | null
  expires_at?: string | null
  created_at: string
  updated_at: string
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'emergency'

export interface RiskAssessment {
  risk_level: RiskLevel
  urgency: string
  confidence: number
  key_findings: string[]
  red_flags_checked: string[]
  red_flags_found: string[]
  next_steps: string[]
  limitations: string[]
  citations: Array<Record<string, unknown>>
}

export interface TriageQuestionnaire {
  questionnaire_id: string
  questions: Array<{
    id: string
    text: string
    type: 'enum' | 'multi' | 'input' | 'number'
    required: boolean
    options?: string[]
  }>
}

export interface TriageTaskResponse {
  task: HealthTask
  questionnaire?: TriageQuestionnaire | null
  result?: RiskAssessment | null
}

export interface KnowledgeCenterItem {
  id: string
  content: string
  metadata: Record<string, unknown>
  score: number
}

export interface KnowledgeDocumentPreview {
  doc_id: string
  title: string
  source: string
  type: string
  disease: string
  version?: string | null
  published_at?: string | null
  reviewed_at?: string | null
  applicable_population?: string | null
  content: string
}

export type ReportStatus =
  | 'uploaded'
  | 'analyzing'
  | 'waiting_confirmation'
  | 'processing'
  | 'completed'
  | 'manual_review'
  | 'failed'
  | 'cancelled'

export interface ReportMeasurement {
  measurement_id: string
  name: string
  value?: string | null
  unit?: string | null
  reference_range?: string | null
  abnormal_flag: 'low' | 'high' | 'normal' | 'unknown'
  confidence: number
  raw_text?: string | null
  user_confirmed: boolean
  unable_to_confirm: boolean
  deleted?: boolean
}

export interface ReportInterpretation {
  confirmed_measurements: Array<Record<string, unknown>>
  explanations: Array<Record<string, unknown>>
  medical_attention: string[]
  limitations: string[]
  citations: Array<Record<string, unknown>>
  safety_decision: string
}

export interface ReportResponse {
  report_id: string
  task: HealthTask
  document_type: 'lab_report' | 'physical_exam' | 'other'
  status: ReportStatus
  image_url: string
  measurements: ReportMeasurement[]
  result?: ReportInterpretation | null
  error?: string | null
  created_at: string
  updated_at: string
}

export interface QuestionnaireData {
  questionnaire_id: string
  questions: QuestionnaireQuestion[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  images?: string[]
  timestamp: string
  isStreaming?: boolean
  assistantMessageId?: string
  traceId?: string
  suggestions?: string[]
  agentEvents?: AgentEvent[]
  thinkingBlocks?: ThinkingBlock[]
  delegations?: TaskDelegation[]
  questionnaire?: QuestionnaireData
  questionnaireError?: string
  citations?: Citation[]
  metadata?: {
    swarmEnabled: boolean
    agentsInvolved: string[]
    /** Client-measured time from request start until the first answer token. */
    timeToFirstToken?: number
    totalTime?: number
    subtasksCompleted?: number
    timeoutOccurred?: boolean
    usage?: {
      prompt_tokens?: number
      completion_tokens?: number
      total_tokens?: number
    }
    performanceMetrics?: {
      parallelEfficiency: number
      informationCoverage: number
      redundancy: number
    }
  }
}

export interface AgentEvent {
  id: string
  type: 'decomposed' | 'start' | 'tool_call' | 'tool_result' | 'complete'
  agentId: string
  subtaskId?: string
  subtaskType?: string
  toolName?: string
  timestamp: string
  data?: Record<string, unknown>
}

export interface TaskDelegation {
  subtaskId: string
  type: string
  description: string
  assignedAgent: string
}

export interface ToolStep {
  toolName: string
  arguments: Record<string, unknown>
  result: string
  success: boolean
  status?: ReasoningStatus
}

export type ReasoningPhase = 'intent' | 'clarify' | 'decompose' | 'synthesize'
export type ReasoningStatus = 'running' | 'waiting' | 'completed' | 'skipped' | 'failed'

export interface ThinkingBlock {
  id: string
  agentId: string
  thinking: string
  iteration: number
  toolSteps: ToolStep[]
  elapsedSeconds?: number
  isCollapsed: boolean
  phase?: ReasoningPhase
  title?: string
  status?: ReasoningStatus
}

export interface KnowledgeItem {
  id: string
  content: string
  metadata: Record<string, string>
  score: number
}

export interface Citation {
  index: number
  doc_id: string
  source: string
  disease: string
  type: string
  filename: string
  score: number
  snippet: string
  content: string
}

export interface DocumentSummary {
  doc_id: string
  filename: string
  type: string
  disease: string
  source: string
  chunk_count: number
}

export interface ChunkDetail {
  milvus_id: number
  chunk_id: number
  content: string
  total_chunks: number
}

export interface SessionItem {
  session_id: string
  first_question: string
  created_at: string
  message_count: number
  mode: string
  total_tokens: number
  parallel_efficiency: number
  information_coverage: number
  redundancy: number
  _isNew?: boolean
}

export interface SessionTurn {
  turn_index: number
  user_message: {
    role: string
    content: string
    images?: string[]
    timestamp?: string
  }
  assistant_message: {
    role: string
    content: string
    timestamp?: string
    agent_events?: unknown[]
    suggestions?: string[]
    mode?: string
    agents_involved?: string[]
    total_time?: number
    time_to_first_token?: number
    total_tokens?: number
    subtasks_completed?: number
    assistant_message_id?: string
    trace_id?: string
  }
}

export interface DashboardStats {
  total_sessions: number
  total_messages: number
  swarm_sessions: number
  single_sessions: number
  avg_response_time: number
  agents_usage: Record<string, number>
  knowledge_base_size: number
  recent_sessions: SessionItem[]
  total_tokens: number
  avg_parallel_efficiency: number
  avg_information_coverage: number
  avg_redundancy: number
  health_task_stats?: {
    total: number
    completion_rate: number
    questionnaire_abandonment_rate: number
    knowledge_empty_rate: number
    report_confirmation_rate: number
    report_failure_rate: number
    by_type: Record<string, number>
    by_status: Record<string, number>
  }
}
