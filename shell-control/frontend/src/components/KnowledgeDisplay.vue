<template>
    <div class="knowledge-display">
      <h3>Knowledge</h3>
      <ul>
        <!-- Recursively render the knowledge dictionary -->
        <li v-for="(value, key) in knowledge" :key="key">
          <strong>{{ key }}:&nbsp;</strong>
          <template v-if="isObject(value)">
            <ul>
              <KnowledgeDisplayList :data="value" />
            </ul>
          </template>
          <template v-else>
            {{ value }}
          </template>
        </li>
      </ul>
    </div>
</template>

<script lang="ts">
  import { defineComponent } from 'vue';
  import KnowledgeDisplayList from './KnowledgeDisplayList.vue'; // Import the recursive helper component

  export default defineComponent({
    name: 'KnowledgeDisplay',
    components: { KnowledgeDisplayList },
    props: {
      knowledge: {
        type: Object,
        required: true,
      },
    },
    methods: {
      isObject(value: any): boolean {
        // Check if the value is an object (for nested dictionaries)
        return value && typeof value === 'object' && !Array.isArray(value);
      },
    },
  });
</script>

<style scoped>
  .knowledge-display {
    padding: 15px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #f9f9f9;
  }

  .knowledge-display h2 {
    margin-bottom: 15px;
  }

  .knowledge-display ul {
    padding-left: 20px;
    list-style-type: disc;
  }

  .knowledge-display li {
    margin-bottom: 5px;
  }
</style>
