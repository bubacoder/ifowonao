<template>
  <div
    :class="['chat-box', boxClass]"
    v-html="event.payload">
  </div>
</template>

<script lang="ts">

import { type PropType } from 'vue';

interface EventData {
  type: 'PROMPT' | 'AI_RESPONSE' | 'COMMAND_RESULT' | 'INFO' | 'WARN' | 'ABORT' | 'COMPLETED';
  payload: any;
}

export default {
  props: {
    event: {
      type: Object as PropType<EventData>,
      required: true
    }
  },
  computed: {
    boxClass() {
      switch (this.event.type) {
        case 'PROMPT':
          return 'prompt';
        case 'AI_RESPONSE':
          return 'ai-response';
        case 'COMMAND_RESULT':
          return 'command-result';
        case 'INFO':
          return 'info';
        case 'WARN':
          return 'warning';
        case 'ABORT':
          return 'error';
        case 'COMPLETED':
          return 'info';
        default:
          return '';
      }
    },
  },
};
</script>
