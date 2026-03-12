import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '/api',
  timeout: 150000,
})

client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || 'Request failed'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default client
