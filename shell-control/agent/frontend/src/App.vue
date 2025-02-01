<template>
  <div id="app">
    <h1># ./shellcontrol.py</h1>
    <PromptExamples
      v-if="!taskStarted"
      @setPrompt="setExamplePrompt"
    />
    <InputPrompt
      v-if="!taskStarted"
      @sendPrompt="sendPrompt"
      :promptValue="prompt"
    />
    <TaskList
      v-if="taskStarted"
      class="floating-task-list"
      :openTasks="tasks.openTasks"
      :completedTasks="tasks.completedTasks"
    />
    <KnowledgeDisplay
      v-if="taskStarted"
      :knowledge="currentKnowledge"
    />
    <div>
      <ChatBox
        v-for="(event, index) in events"
        :key="index"
        :event="event"
      />
    </div>
    <LoadingBar
      :visible="taskRunning"
      color="#ff6f61"
    />
    <TerminateButton
      v-if="taskRunning"
    />
  </div>
</template>

<script lang="ts">
import { ref, reactive, type Ref } from 'vue';
import { type EventData } from './types/events';
import ChatBox from './components/ChatBox.vue';
import InputPrompt from './components/InputPrompt.vue';
import PromptExamples from './components/PromptExamples.vue';
import TaskList from './components/TaskList.vue';
import LoadingBar from './components/LoadingBar.vue';
import KnowledgeDisplay from './components/KnowledgeDisplay.vue';
import TerminateButton from './components/TerminateButton.vue';

function formatCommandResult(commandResult: any): string {
  const output = commandResult.output || "(The command produced no output)";
  const error = commandResult.error || "(The command produced no error output)";
  const additionalError = commandResult.additional_error || "";
  const returnCode = commandResult.returncode || 0;

  let formattedOutput = `#️⃣ <b>Command output</b><br/>${output}<br/><br/>`;
  if (returnCode !== 0) {
    formattedOutput += `<b>Errors</b><br/>${error + (additionalError ? `<br/>${additionalError}` : "")}</br><br/>`;
  }
  formattedOutput += `<b>Return code:</b> ${returnCode}`;
  return formattedOutput;
}

function formatAIResponse(previous_action_results: string | null, next_action: string | null, tool_to_use: string | null): string {
  let responseFormatted = "";

  if (previous_action_results) {
    responseFormatted += `⬆️ <b>Interpretation of previous action</b><br/>${previous_action_results}<br/><br/>`;
  }
  if (next_action) {
    responseFormatted += `⬇️ <b>Next action</b><br/>${next_action}<br/><br/>`;
  }
  if (tool_to_use) {
    responseFormatted += `#️⃣ <b>Next tool to run</b><br/>${JSON.stringify(tool_to_use, null, 2)}<br/>`;
  }

  return responseFormatted;
}

function getWebSocketUrl(): string {
  const { protocol, hostname, port } = window.location;
  const wsProtocol = protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProtocol}//${hostname}${port ? `:${port}` : ""}/ws`;
  return wsUrl;
}

export default {
  components: {
    ChatBox,
    InputPrompt,
    PromptExamples,
    TaskList,
    LoadingBar,
    KnowledgeDisplay,
    TerminateButton,
  },
  setup() {
    // Define the types for the ref variables
    const events: Ref<EventData[]> = ref([]);
    const prompt: Ref<string> = ref("");
    const taskStarted: Ref<boolean> = ref(false);
    const taskRunning = ref(false);
    const currentKnowledge = ref({});
    const ws = new WebSocket(getWebSocketUrl());

    // Store open and completed tasks in a reactive object
    const tasks = reactive({
      openTasks: [] as string[],
      completedTasks: [] as string[],
    });

    // Handle incoming WebSocket messages
    ws.onmessage = (message: MessageEvent) => {
      const event = JSON.parse(message.data) as EventData;

      switch (event.type) {
        case "AI_RESPONSE":
          if (typeof event.payload === "object" && event.payload !== null) {
            const { knowledge, open_tasks, completed_tasks, previous_action_results, next_action, tool_to_use } = event.payload;

            // Update task list and knowledge display
            if (open_tasks) { tasks.openTasks = open_tasks; }
            if (completed_tasks) { tasks.completedTasks = completed_tasks; }
            if (knowledge) { currentKnowledge.value = knowledge; }

            const response_formatted = formatAIResponse(previous_action_results, next_action, tool_to_use);
            events.value.push({ type: "AI_RESPONSE", payload: response_formatted });
          } else {
            events.value.push(event);
          }
          break;

        case "TOOL_SUCCESS":
          if (event.payload.returncode !== undefined) {
            const formattedResult = formatCommandResult(event.payload);
            events.value.push({ type: "TOOL_SUCCESS", payload: formattedResult });
          } else {
            events.value.push(event);
          }
          break;

        case "TOOL_ERROR":
          events.value.push(event);
          break;

        case "COMPLETED":
          const completed_message: string =
            "✅ <b>The AI has completed the task.</b><br/><br/>" +
            (event.payload !== null ? event.payload : "") +
            "<br/><br/><i>Reload the page for a new task.</i>";
          events.value.push({ type: "COMPLETED", payload: completed_message });
          taskRunning.value = false;
          break;

        case "ABORT":
          events.value.push(event);
          taskRunning.value = false;
          break;

        default:
          events.value.push(event);
          break;
      }
    };

    ws.onerror = (error: Event) => {
      events.value.push({
        type: "ABORT",
        payload: `WebSocket error: ${(error as ErrorEvent).message}`,
      });
      taskRunning.value = false;
    };

    ws.onclose = () => {
      events.value.push({
        type: "INFO",
        payload: "WebSocket connection closed.",
      });
      taskRunning.value = false;
    };

    // Send the prompt via WebSocket
    const sendPrompt = (userPrompt: string): void => {
      if (ws.readyState === WebSocket.OPEN) {
        events.value.push({
          type: "PROMPT",
          payload: "💬 " + userPrompt,
        });
        ws.send(JSON.stringify({
          type: "prompt",
          payload: userPrompt
        }));
        taskStarted.value = true;
        taskRunning.value = true;
      } else {
        events.value.push({
          type: "ABORT",
          payload: "WebSocket not connected. Please try again later.",
        });
      }
    };

    const setExamplePrompt = (example: string): void => {
      prompt.value = example;
    };

    return {
      events,
      prompt,
      sendPrompt,
      setExamplePrompt,
      taskStarted,
      taskRunning,
      tasks,
      currentKnowledge,
    };
  },
};
</script>
