import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Stage Coach. Upload or record a talk. Get research-backed feedback.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const icon = await readFile(path.join(process.cwd(), "public/brand/app-icon-dark-1024.png"));
  const src = `data:image/png;base64,${icon.toString("base64")}`;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          background: "#000000",
          color: "#F0F0FA",
          padding: "80px",
        }}
      >
        <img src={src} width={120} height={120} alt="" />
        <div style={{ fontSize: 22, letterSpacing: 4, marginTop: 28 }}>CYBERSPHERE</div>
        <div style={{ fontSize: 84, fontWeight: 700, letterSpacing: 1, marginTop: 12 }}>STAGE COACH</div>
        <div style={{ fontSize: 32, marginTop: 24, color: "#C6C7D0" }}>
          Upload or record a talk. Get research-backed feedback.
        </div>
      </div>
    ),
    { ...size },
  );
}
