<template>
    <div
      v-if="visible"
      class="loading-bar-container"
    >
      <div
        class="loading-bar"
        :style="{ background: color }"
      ></div>
    </div>
  </template>

  <script lang="ts">
  import { defineComponent } from 'vue';

  export default defineComponent({
    name: 'LoadingBar',
    props: {
      visible: {
        type: Boolean,
        required: true,
      },
      color: {
        type: String,
        required: false,
        default: '#3498db', // Default blue color
      },
    },
  });
  </script>

  <style scoped>
  /* The container for the bar - gives it height and an overflow hidden */
  .loading-bar-container {
    position: relative;
    width: 100%;
    height: 4px; /* height of the loading bar */
    overflow: hidden;
    background-color: #e0e0e0; /* gray background as contrast */
  }

  /* The animated loading bar */
  .loading-bar {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 100%;
    animation: infinite-loading 2s infinite linear;
  }

  /* Keyframes to continuously move the bar */
  @keyframes infinite-loading {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }
  </style>
