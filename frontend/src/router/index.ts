import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/search', name: 'Search', component: () => import('../views/Search.vue') },
    { path: '/users', name: 'Users', component: () => import('../views/Users.vue') },
    { path: '/works', name: 'Works', component: () => import('../views/Works.vue') },
    { path: '/tasks', name: 'Tasks', component: () => import('../views/Tasks.vue') },
    { path: '/schedules', name: 'Schedules', component: () => import('../views/Schedules.vue') },
    { path: '/logs', name: 'Logs', component: () => import('../views/Logs.vue') },
    { path: '/sessions', name: 'Sessions', component: () => import('../views/Sessions.vue') },
  ],
})

export default router
