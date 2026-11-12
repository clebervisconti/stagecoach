export type PrivacyCopy = {
  title: string;
  back: string;
  paragraphs: readonly string[];
};

const EN: PrivacyCopy = {
  title: "Privacy",
  back: "Back to sign in",
  paragraphs: [
    "Stage Coach uses Splunk Real User Monitoring (RUM) to measure how pages load.",
    "The session id is stored in localStorage. There is no Splunk cookie and no anonymous user id.",
    "Geolocation is derived at ingestion as a country code. The raw IP is not kept for Splunk Observability or dashboards.",
    "Session replay is off and is not loaded. Forms and user IDs are not captured.",
    "Telemetry does not include the transcript, the media path, or the raw URL. Query strings and fragments are removed, and email addresses are redacted, before a span is exported.",
    "A browser Do Not Track or Global Privacy Control signal skips RUM. Starting RUM does not ask for an acceptance click.",
  ],
};

const PT_BR: PrivacyCopy = {
  title: "Privacidade",
  back: "Voltar para entrar",
  paragraphs: [
    "O Stage Coach usa o Splunk Real User Monitoring (RUM) para medir como as páginas carregam.",
    "O identificador de sessão fica no localStorage. Não há cookie do Splunk e não há identificador anônimo de usuário.",
    "A geolocalização é derivada na ingestão como um código de país. O IP bruto não é mantido no Splunk Observability nem nos painéis.",
    "A reprodução de sessão está desligada e não é carregada. Formulários e identificadores de usuário não são capturados.",
    "A telemetria não inclui a transcrição, o caminho da mídia nem a URL bruta. As consultas e os fragmentos são removidos, e os endereços de e-mail são ocultados, antes de um span ser exportado.",
    "Os sinais Do Not Track e Global Privacy Control do navegador desligam o RUM. Ligar o RUM não pede um clique de aceite.",
  ],
};

export function privacyPolicy(locale: string): PrivacyCopy {
  return locale === "pt-BR" ? PT_BR : EN;
}
