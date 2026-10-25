import axios, { AxiosError } from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "";

const http = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data;
    if (data && typeof data === "object") {
      const body = data as {
        message?: unknown;
        error?: { message?: unknown };
      };
      if (typeof body.error?.message === "string") return body.error.message;
      if (typeof body.message === "string") return body.message;
    }
    if (error.code === "ECONNABORTED") return "请求超时，请稍后重试";
    if (error.message === "Network Error") return "网络异常，请检查连接";
  }
  return error instanceof Error ? error.message : "请求失败，请稍后重试";
}

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
