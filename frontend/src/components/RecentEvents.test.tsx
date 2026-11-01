import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RecentEvents from "./RecentEvents";
import { getEvents } from "../api/cameraApi";
import type { DetectionEvent } from "../api/types";

jest.mock("../api/cameraApi", () => ({
  getEvents: jest.fn(),
}));

jest.mock("../api/itemApi", () => ({
  getImageUrl: (path: string) => path,
}));

const createEvent = (frameId: string): DetectionEvent => ({
  event_id: "event-1",
  frame_id: frameId,
  camera_id: "camera-1",
  room: "客厅",
  class_name: "cup",
  confidence: 0.9,
  bbox: [1, 2, 30, 40],
  captured_at: "2026-10-27T02:00:00Z",
  model_version: "fake-demo-1",
  raw_image_path: "images/event.jpg",
  annotated_image_path: "processed_images/event.jpg",
  annotated_image_url: "/api/events/event-1/annotation",
});

describe("RecentEvents", () => {
  it("reloads the representative image when the same event receives a new frame", async () => {
    const getEventsMock = jest.mocked(getEvents);
    getEventsMock
      .mockResolvedValueOnce({ events: [createEvent("frame-1")], total: 1, limit: 5, offset: 0 })
      .mockResolvedValueOnce({ events: [createEvent("frame-2")], total: 1, limit: 5, offset: 0 });

    render(<RecentEvents />);
    const image = await screen.findByAltText("cup 检测标注图");
    const firstSource = image.getAttribute("src");
    expect(firstSource).toContain("_frame=frame-1");

    fireEvent.click(screen.getByRole("button", { name: "刷新事件列表" }));

    await waitFor(() => {
      expect(screen.getByAltText("cup 检测标注图").getAttribute("src")).toContain("_frame=frame-2");
    });
  });
});
