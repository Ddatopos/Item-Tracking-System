import React from "react";
import { render, screen } from "@testing-library/react";
import { getEvents, getHealth } from "../api/cameraApi";
import OverviewPage from "./OverviewPage";

jest.mock("../api/cameraApi", () => ({
  getHealth: jest.fn(),
  getPreviewUrl: jest.fn(() => "/api/stream/preview"),
  startPreview: jest.fn(),
  stopPreview: jest.fn(),
  getEvents: jest.fn(),
}));

jest.mock("../api/itemApi", () => ({
  getImageUrl: (path: string) => path,
}));

describe("OverviewPage", () => {
  beforeEach(() => {
    jest.mocked(getHealth).mockResolvedValue({
      service_status: "ok",
      status: "offline",
      cameras: [{
        camera_id: "camera-1",
        room: "客厅",
        status: "offline",
        source_type: "mock",
        resolution: "unknown",
      }],
      stream: { preview_url: "/api/stream/preview", status: "stopped" },
      inference: { status: "idle", model_version: "fake-demo-1", fps: 0 },
    });
    jest.mocked(getEvents).mockResolvedValue({
      events: [],
      total: 0,
      limit: 5,
      offset: 0,
    });
  });

  it("shows a healthy backend while the camera is offline", async () => {
    render(<OverviewPage />);

    expect(await screen.findByLabelText("在线")).toBeInTheDocument();
    expect(screen.getByLabelText("客厅 离线")).toBeInTheDocument();
  });
});
