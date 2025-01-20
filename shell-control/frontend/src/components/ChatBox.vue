<template>
  <div
    :class="['chat-box', boxClass]"
    v-html="event.payload">
  </div>
</template>

<script lang="ts">
export default {
  props: ['event'],
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
