<template>
    <ul>
      <li v-for="(value, key) in data" :key="key">
        <strong>{{ key }}:&nbsp;</strong>
        <template v-if="isObject(value)">
          <ul>
            <KnowledgeDisplayList :data="value" />
          </ul>
        </template>
        <template v-else>
          <span v-text="value"></span>
        </template>
      </li>
    </ul>
</template>

<script lang="ts">
  import { defineComponent } from 'vue';

  export default defineComponent({
    name: 'KnowledgeDisplayList',
    props: {
      data: {
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
ul {
  list-style-type: disc;
  padding-left: 20px;
}
</style>
