import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FarmerHome from "../FarmerHome";
import { ScannerPage } from "../MainPages";
import Navigation from "../Navigation";
import ReportsPage from "../ReportsPage";
import DiagnosisResult from "../DiagnosisResult";
import useWebSocket from "../../hooks/useWebSocket";
import { diagnoseImage } from "../../services/api";
import { validatePhotoFile } from "../../services/photoInput";
import { renderHook } from "@testing-library/react";

function homeProps(overrides = {}) {
  return {
    language: "en",
    backendState: "healthy",
    diagnosisAvailable: true,
    diagnosisUnavailableReason: "",
    reports: [],
    reportsLoading: false,
    reportsError: "",
    onTakePhoto: vi.fn(),
    onChoosePhoto: vi.fn(),
    onNavigate: vi.fn(),
    ...overrides,
  };
}

function scannerProps(overrides = {}) {
  return {
    selectedFile: null,
    preview: null,
    result: null,
    loading: false,
    error: "",
    backendState: "healthy",
    diagnosisAvailable: true,
    diagnosisUnavailableReason: "",
    language: "en",
    onTakePhoto: vi.fn(),
    onChoosePhoto: vi.fn(),
    onDiagnose: vi.fn(),
    onReset: vi.fn(),
    onRetryConnection: vi.fn(),
    ...overrides,
  };
}

describe("farmer photo workflows", () => {
  it("offers native camera and gallery actions from home", async () => {
    const user = userEvent.setup();
    const props = homeProps();
    render(<FarmerHome {...props} />);

    await user.click(screen.getByRole("button", { name: /take a photo/i }));
    await user.click(screen.getByRole("button", { name: /choose from gallery/i }));
    expect(props.onTakePhoto).toHaveBeenCalledOnce();
    expect(props.onChoosePhoto).toHaveBeenCalledOnce();
  });

  it("keeps the photo preview available and supports retake or replacement", async () => {
    const user = userEvent.setup();
    const file = new File(["photo"], "leaf.jpg", { type: "image/jpeg" });
    const props = scannerProps({ selectedFile: file, preview: "blob:leaf-preview" });
    render(<ScannerPage {...props} />);

    expect(screen.getByRole("img", { name: /preview of the crop photo/i })).toHaveAttribute("src", "blob:leaf-preview");
    await user.click(screen.getByRole("button", { name: /take another photo/i }));
    await user.click(screen.getByRole("button", { name: /choose another photo/i }));
    expect(props.onTakePhoto).toHaveBeenCalledOnce();
    expect(props.onChoosePhoto).toHaveBeenCalledOnce();
  });

  it("shows image upload errors and disables duplicate analysis while loading", () => {
    const file = new File(["photo"], "leaf.jpg", { type: "image/jpeg" });
    const onDiagnose = vi.fn();
    const props = scannerProps({ selectedFile: file, error: "This photo could not be opened.", loading: true, onDiagnose });
    render(<ScannerPage {...props} />);

    expect(screen.getByRole("alert")).toHaveTextContent("This photo could not be opened.");
    const checkButton = screen.getByRole("button", { name: /checking your photo/i });
    expect(checkButton).toBeDisabled();
    fireEvent.click(checkButton);
    expect(onDiagnose).not.toHaveBeenCalled();
  });

  it("renders a not-plant rejection without showing a disease name", async () => {
    const user = userEvent.setup();
    const onCheckAnother = vi.fn();
    render(<DiagnosisResult result={{ status: "not_plant", message: "This is not a crop photo." }} onCheckAnother={onCheckAnother} />);

    expect(screen.getByRole("heading", { name: /doesn’t look like a crop photo/i })).toBeInTheDocument();
    expect(screen.getByText(/no crop disease was identified/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /check a crop/i }));
    expect(onCheckAnother).toHaveBeenCalledOnce();
  });

  it("renders uncertainty without inventing a crop or diagnosis", () => {
    render(<DiagnosisResult result={{
      status: "uncertain",
      crop: null,
      diagnosis: null,
      confidence: 84,
      message: "The image is suitable, but the model could not confirm a condition.",
      prevention: [],
    }} onCheckAnother={vi.fn()} />);

    expect(screen.getByRole("heading", { name: /couldn’t confirm a crop condition/i })).toBeInTheDocument();
    expect(screen.getByText(/could not confirm a condition/i)).toBeInTheDocument();
    expect(screen.queryByText(/84\.0%/)).not.toBeInTheDocument();
  });

  it("renders an accepted result with its limitations and next steps", () => {
    render(<DiagnosisResult result={{
      status: "possible_disease_detected",
      crop: "Tomato",
      diagnosis: "Early Blight",
      confidence: 86.2,
      severity: "Moderate",
      symptoms: "Dark leaf spots.",
      prevention: ["Remove affected leaves."],
      expert_review: true,
    }} onCheckAnother={vi.fn()} />);

    expect(screen.getByRole("heading", { name: /possible disease detected/i })).toBeInTheDocument();
    expect(screen.getByText(/Tomato · Early Blight/)).toBeInTheDocument();
    expect(screen.getByText(/86\.2%/)).toBeInTheDocument();
    expect(screen.getByText(/Remove affected leaves/)).toBeInTheDocument();
  });

  it("shows the four primary mobile destinations and navigates from them", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<Navigation page="home" onNavigate={onNavigate} language="en" />);
    const [desktop, mobile] = screen.getAllByRole("navigation", { name: "Main navigation" });
    expect(desktop).toBeInTheDocument();
    for (const label of ["Home", "Check crop", "My reports", "Help"]) {
      expect(mobile).toHaveTextContent(label);
    }
    await user.click(mobile.querySelector("button[aria-current='page']"));
    expect(onNavigate).toHaveBeenCalledWith("home");
  });

  it("shows an empty reports state and offers a working next action", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(<ReportsPage language="en" reports={[]} loading={false} error="" onNavigate={onNavigate} onRetry={vi.fn()} />);

    expect(screen.getByText(/reports will appear here/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /check a crop/i }));
    expect(onNavigate).toHaveBeenCalledWith("scanner");
  });
});

describe("API and realtime behavior", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("preserves a structured non-plant response from the API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: "not_plant",
      message: "This is not a crop photo.",
      validation: { score: 0.12 },
    }), { status: 422, headers: { "Content-Type": "application/json" } })));
    const file = new File(["pixels"], "photo.jpg", { type: "image/jpeg" });

    await expect(diagnoseImage(file)).resolves.toMatchObject({ status: "not_plant", validation: { score: 0.12 } });
    const [, request] = fetch.mock.calls[0];
    expect(request.method).toBe("POST");
    expect(request.headers["X-Report-Key"]).toHaveLength(64);
    expect(request.headers["Content-Type"]).toBeUndefined();
  });

  it("orients, downsizes, and JPEG-encodes valid photos under the upload limit", async () => {
    const bitmap = { width: 2400, height: 1200, close: vi.fn() };
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue(bitmap));
    const drawImage = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      fillRect: vi.fn(),
      drawImage,
    });
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
      callback(new Blob(["encoded photo"], { type: "image/jpeg" }));
    });

    const file = new File([new Uint8Array(4 * 1024 * 1024 + 1)], "leaf.png", { type: "image/png" });
    const normalized = await validatePhotoFile(file);
    expect(normalized.type).toBe("image/jpeg");
    expect(normalized.name).toBe("leaf.jpg");
    expect(normalized.size).toBeLessThan(4 * 1024 * 1024);
    expect(createImageBitmap).toHaveBeenCalledWith(file, { imageOrientation: "from-image" });
    expect(drawImage).toHaveBeenCalledWith(bitmap, 0, 0, 1024, 512);
    expect(bitmap.close).toHaveBeenCalledOnce();

    await expect(validatePhotoFile(new File(["gif"], "leaf.gif", { type: "image/gif" })))
      .rejects.toThrow(/JPG or PNG/);

    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue({ width: 9000, height: 9000, close: vi.fn() }));
    await expect(validatePhotoFile(new File(["large dimensions"], "huge.png", { type: "image/png" })))
      .rejects.toThrow(/fewer pixels/);
  });

  it("marks a WebSocket disconnect, reconnects, and cleans up on unmount", () => {
    vi.useFakeTimers();
    class MockWebSocket {
      static instances = [];
      constructor() { MockWebSocket.instances.push(this); }
      close() { this.onclose?.(); }
    }
    vi.stubGlobal("WebSocket", MockWebSocket);
    const onEvent = vi.fn();
    const onStatusChange = vi.fn();
    const { unmount } = renderHook(() => useWebSocket({ onEvent, onStatusChange }));
    const first = MockWebSocket.instances[0];

    act(() => first.onopen());
    expect(onStatusChange).toHaveBeenLastCalledWith("live");
    act(() => first.onclose());
    expect(onStatusChange).toHaveBeenLastCalledWith("offline");
    act(() => vi.advanceTimersByTime(1000));
    expect(MockWebSocket.instances).toHaveLength(2);

    unmount();
    expect(MockWebSocket.instances[1].onclose).toBeTypeOf("function");
  });
});
