import axios, { AxiosError } from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "";

const http = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.code === "ECONNABORTED") {
      return Promise.reject(new Error("请求超时，请稍后重试"));
    }
    if (error.message === "Network Error") {
      return Promise.reject(new Error("网络异常，请检查连接"));
    }
    return Promise.reject(error);
  }
);

export { API_BASE };
export default http;
