<template>
    <div class="terminate-button-container">
      <button
        v-if="!clicked"
        class="terminate-button"
        @click="handleClick"
      >
        SIGTERM
      </button>
      <p v-if="clicked" class="terminate-message">
        <strong>All processes being terminated. Wait a few seconds before reloading the page.</strong>
      </p>
    </div>
</template>

<script lang="ts">
  import { ref } from 'vue';
  import axios from 'axios';

  export default {
    name: 'TerminateButton',
    setup() {
      const clicked = ref(false);

      const handleClick = () => {
        clicked.value = true; // Disable the button and show the message

        // Send a POST request to the server without waiting for a response
        axios.post('/terminate').catch((error) => {
          console.error('Error sending SIGTERM request:', error);
        });
      };

      return {
        clicked,
        handleClick,
      };
    },
  };
</script>

<style scoped>
  /* SIGTERM Button styles */
  .terminate-button-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-top: 20px;
  }

  .terminate-button {
    background-color: red;
    color: white;
    border: none;
    padding: 10px 20px;
    font-size: 16px;
    cursor: pointer;
    border-radius: 5px;
  }

  .terminate-button:hover {
    background-color: darkred;
  }

  .terminate-message {
    margin-top: 10px;
    font-size: 16px;
    color: #ff6f61;
    text-align: center;
  }
</style>
