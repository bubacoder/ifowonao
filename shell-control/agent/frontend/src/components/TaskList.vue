<template>
  <div>
    <h3>Plan</h3>
    <div>
    <ul>
      <li v-for="(task, index) in completedTasks" :key="'completed-task-' + index">
      <input type="checkbox" :checked="true" disabled />
      <span>{{ task }}</span>
      </li>
    </ul>
    <ul>
      <li v-for="(task, index) in openTasks" :key="'open-task-' + index">
      <input type="checkbox" :checked="false" disabled />
      <span>{{ task }}</span>
      </li>
    </ul>
    </div>
  </div>
</template>

<script lang="ts">
  import { defineComponent, type PropType } from 'vue';

  export default defineComponent({
    name: 'TaskList',
    props: {
      openTasks: {
        type: Array as PropType<string[]>,
        required: true,
      },
      completedTasks: {
        type: Array as PropType<string[]>,
        required: true,
      },
    },
  });
</script>
