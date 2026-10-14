// Sends traces, metrics, and logs to the host OTel collector.
// The collector holds the Splunk token; this process never does.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  if (process.env.NEXT_PHASE === "phase-production-build") return;
  if (process.env.OTEL_ENABLED === "false") return;

  try {
    const { start } = await import("@splunk/otel");
    start({
      serviceName: process.env.OTEL_SERVICE_NAME || "stagecoach",
      endpoint:
        process.env.OTEL_EXPORTER_OTLP_ENDPOINT || "http://127.0.0.1:4318",
      tracing: true,
      metrics: true,
      logging: true,
      profiling: false,
    });
  } catch (error) {
    console.error("OpenTelemetry failed to start", error);
  }
}
