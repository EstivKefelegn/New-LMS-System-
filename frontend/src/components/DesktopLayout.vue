<template>
  <div class="flex h-screen w-screen">
    <!-- Only show sidebar if user is NOT an LMS Student -->
    <div v-if="isAdmin" class="h-full border-r bg-surface-menu-bar">
      <AppSidebar />
    </div>

    <div class="flex-1 flex flex-col h-full overflow-auto bg-surface-white">
      <slot />
    </div>
  </div>
</template>

<script setup>
import AppSidebar from './AppSidebar.vue'
import { usersStore } from '@/stores/user'
import { computed } from 'vue'

const { userResource } = usersStore()

// Computed property to check if the user has LMS Student role
const isAdmin = computed(() => {
  return userResource.data?.roles?.includes('Administrator')
})

</script>
