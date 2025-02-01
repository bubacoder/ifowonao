export interface EventData {
  type: 'PROMPT' | 'AI_RESPONSE' | 'TOOL_SUCCESS' | 'TOOL_ERROR' | 'INFO' | 'WARN' | 'ABORT' | 'COMPLETED';
  payload: any;
}
