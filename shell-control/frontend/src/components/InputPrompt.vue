<template>
  <div class="input-prompt">
    <input
      v-model="inputValue"
      type="text"
      placeholder="Enter your prompt..."
    />
    <button @click="submitPrompt">Send</button>
  </div>
</template>

<script lang="ts">
import { ref, watch } from 'vue';

export default {
  props: ['promptValue'],
  emits: ['sendPrompt'],
  setup(props, { emit }) {
    const inputValue = ref(props.promptValue);

    // Update the input value when promptValue changes
    watch(() => props.promptValue, (newValue) => {
      inputValue.value = newValue;
    });

    const submitPrompt = () => {
      if (inputValue.value.trim()) {
        emit('sendPrompt', inputValue.value.trim());
        inputValue.value = '';
      }
    };

    return { inputValue, submitPrompt };
  },
};
</script>
