import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import MJPEGPreview from "./MJPEGPreview";

describe("MJPEGPreview", () => {
  it("clears an old image error after the preview is stopped and restarted", () => {
    const onRetry = jest.fn();
    const { rerender } = render(
      <MJPEGPreview previewUrl="/api/stream/preview" status="playing" onRetry={onRetry} />
    );

    fireEvent.error(screen.getByAltText("摄像头实时预览"));
    expect(screen.getByText("视频流加载失败")).toBeInTheDocument();

    rerender(
      <MJPEGPreview previewUrl="/api/stream/preview" status="stopped" onRetry={onRetry} />
    );
    rerender(
      <MJPEGPreview previewUrl="/api/stream/preview" status="playing" onRetry={onRetry} />
    );

    expect(screen.getByAltText("摄像头实时预览")).toBeInTheDocument();
    expect(screen.queryByText("视频流加载失败")).not.toBeInTheDocument();
  });

  it("delegates retry to the parent so it can restart the backend preview", () => {
    const onRetry = jest.fn();
    render(<MJPEGPreview previewUrl="/api/stream/preview" status="error" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
