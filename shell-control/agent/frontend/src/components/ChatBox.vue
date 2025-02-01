<template>
  <div
    :class="['chat-box', boxClass]"
    v-html="event.payload">
  </div>
</template>

<script lang="ts">

import { type PropType } from 'vue';
import { type EventData } from '../types/events';

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
        case 'TOOL_SUCCESS':
          return 'tool-success';
        case 'TOOL_ERROR':
          return 'warning';
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
