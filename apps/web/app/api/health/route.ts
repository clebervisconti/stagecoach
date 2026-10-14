export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({
    status: "healthy",
    service: "stagecoach",
    version: "0.2.0",
  });
}
