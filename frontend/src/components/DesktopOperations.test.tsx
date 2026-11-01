import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import DesktopOperations from "./DesktopOperations";
import type { DesktopApi } from "../api/types";

const createApi = (): jest.Mocked<DesktopApi> => ({
  start: jest.fn().mockResolvedValue({ ok: false, message: "启动器未接入" }),
  stop: jest.fn().mockResolvedValue({ ok: true, message: "已停止" }),
  open_data_dir: jest.fn().mockResolvedValue({ ok: true, message: "已打开" }),
  export_logs: jest.fn().mockResolvedValue({ ok: true, message: "已导出" }),
  set_data_dir: jest.fn().mockResolvedValue({ ok: true, message: "下次启动生效" }),
  shutdown: jest.fn().mockResolvedValue({ ok: true, message: "已退出" }),
  select_data_dir: jest.fn().mockResolvedValue({
    ok: true,
    message: "已选择",
    data: { path: "C:\\tracking-data" },
  }),
  select_export_destination: jest.fn().mockResolvedValue({
    ok: true,
    message: "已选择",
    data: { path: "C:\\exports\\logs.zip" },
  }),
});

describe("DesktopOperations", () => {
  afterEach(() => {
    delete window.pywebview;
  });

  it("uses the agreed bridge methods and reports launcher failures", async () => {
    const api = createApi();
    window.pywebview = { api };
    render(<DesktopOperations />);

    fireEvent.click(await screen.findByRole("button", { name: "选择数据目录" }));
    await waitFor(() => expect(api.set_data_dir).toHaveBeenCalledWith("C:\\tracking-data"));

    fireEvent.click(screen.getByRole("button", { name: "导出日志" }));
    await waitFor(() => {
      expect(api.export_logs).toHaveBeenCalledWith("C:\\exports\\logs.zip");
    });

    fireEvent.click(screen.getByRole("button", { name: "启动后台" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("启动器未接入");
  });
});
