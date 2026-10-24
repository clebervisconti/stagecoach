/** Human labels for scoring-config metric ids. Keys stay in the report JSON. */

const LABELS: Record<string, readonly [string, string]> = {
  cm_message_identifiable: ["Identifiable message", "Mensagem identificável"],
  cm_claim_not_topic: ["Claim, not just a topic", "Afirmação, não só um tema"],
  cm_time_to_message_s: ["Time to the message", "Tempo até a mensagem"],
  cm_reinforcement_count: ["Message reinforcements", "Reforços da mensagem"],
  cm_cta_specificity: ["Call to action", "Chamada para ação"],
  st_outline_clarity: ["Outline clarity", "Clareza do roteiro"],
  st_main_points_count: ["Main points", "Pontos principais"],
  st_signposts_per_boundary: ["Signposts", "Sinalizações"],
  st_logical_flow: ["Logical flow", "Fluxo lógico"],
  st_recap_present: ["Recap", "Recapitulação"],
  sto_story_units: ["Stories", "Histórias"],
  sto_story_quality: ["Story quality", "Qualidade da história"],
  sto_concreteness: ["Concreteness", "Concreção"],
  sto_contrast_moves_per_10min: ["Contrasts per 10 min", "Contrastes por 10 min"],
  sto_novelty_moment: ["Novelty", "Novidade"],
  aud_relevance_framing: ["Relevance framing", "Enquadramento de relevância"],
  aud_depth_fit: ["Depth for the audience", "Profundidade para a audiência"],
  aud_jargon_undefined_per_10min: ["Undefined jargon per 10 min", "Jargão sem definição por 10 min"],
  aud_speaker_centric_ratio: ["Speaker-centric share", "Fala centrada em quem fala"],
  aud_live_adaptation: ["Live adaptation", "Adaptação ao vivo"],
  oc_hook_quality: ["Opening hook", "Gancho de abertura"],
  oc_time_to_relevance_s: ["Time to relevance", "Tempo até a relevância"],
  oc_throat_clearing_s: ["Throat-clearing", "Introdução vazia"],
  oc_close_recap: ["Closing recap", "Recapitulação final"],
  oc_close_cta: ["Closing call to action", "Chamada final"],
  oc_ending_quality: ["Ending", "Encerramento"],
  cl_bluf: ["Bottom line up front", "Conclusão no início"],
  cl_claims_supported_ratio: ["Supported claims", "Afirmações sustentadas"],
  cl_mean_sentence_words: ["Mean sentence length", "Tamanho médio da frase"],
  cl_long_sentence_ratio: ["Long sentences", "Frases longas"],
  cl_redundancy_ratio: ["Redundancy", "Redundância"],
  cl_vagueness_per_100w: ["Vagueness per 100 words", "Vaguidade por 100 palavras"],
  cl_precision_llm: ["Precision", "Precisão"],
  imp_clt_density: ["Concrete language", "Linguagem concreta"],
  imp_clt_diversity: ["Language variety", "Variedade de linguagem"],
  imp_success_profile: ["Success profile", "Perfil de sucesso"],
  imp_memorable_moment: ["Memorable moment", "Momento memorável"],
  imp_cta_strength: ["Call to action strength", "Força da chamada"],
  va_words_per_slide_median: ["Words per slide", "Palavras por slide"],
  va_dense_slide_ratio: ["Dense slides", "Slides densos"],
  va_assertion_headline_ratio: ["Assertion headlines", "Títulos com afirmação"],
  va_reading_ratio: ["Reading the slides", "Leitura dos slides"],
  va_screen_facing_s_per_min: ["Time facing the screen", "Tempo de frente para a tela"],
  va_glance_llm: ["Glance test", "Teste de relance"],
  pp_wpm: ["Words per minute", "Palavras por minuto"],
  pp_articulation_rate_sps: ["Articulation rate", "Taxa de articulação"],
  pp_pace_cv: ["Pace variation", "Variação de ritmo"],
  pp_rush_index: ["Rush index", "Índice de pressa"],
  pp_boundary_pause_ratio: ["Pauses at boundaries", "Pausas nas transições"],
  pp_unplanned_long_pauses_per_10min: ["Long pauses per 10 min", "Pausas longas por 10 min"],
  pp_mean_length_of_run: ["Mean length of run", "Duração média da fala"],
  vv_pvq_median: ["Pitch variation", "Variação de tom"],
  vv_pitch_range_st: ["Pitch range", "Extensão de tom"],
  vv_monotone_windows_ratio: ["Monotone stretches", "Trechos monótonos"],
  vv_intensity_variation_db: ["Loudness variation", "Variação de volume"],
  vv_emphasis_rate_per_min: ["Emphasis per minute", "Ênfases por minuto"],
  fl_filler_sounds_per_min: ["Filler sounds per minute", "Sons de preenchimento por minuto"],
  fl_filler_words_per_min: ["Filler words per minute", "Palavras de preenchimento por minuto"],
  fl_hedges_apologies_per_10min: ["Hedges per 10 min", "Ressalvas por 10 min"],
  fl_repetitions_restarts_per_min: ["Restarts per minute", "Recomeços por minuto"],
  fl_grammar_llm: ["Grammar", "Gramática"],
  gb_gesture_activity_ratio: ["Gesture activity", "Atividade gestual"],
  gb_gesture_space_ratio: ["Gesture space", "Espaço dos gestos"],
  gb_gesture_speech_sync: ["Gesture and speech sync", "Sincronia gesto e fala"],
  gb_self_adaptor_per_min: ["Self-adaptors per minute", "Autoadaptadores por minuto"],
  gb_closed_posture_ratio: ["Closed posture", "Postura fechada"],
  gb_sway_index: ["Sway", "Balanço"],
  gb_purposeful_movement: ["Purposeful movement", "Movimento com propósito"],
  ec_audience_facing_ratio: ["Audience-facing time", "Tempo de frente para a audiência"],
  ec_gaze_distribution_evenness: ["Gaze spread", "Distribuição do olhar"],
  ec_gaze_holds_per_min: ["Gaze holds per minute", "Manutenções do olhar por minuto"],
  ec_reading_head_down_ratio: ["Head-down time", "Tempo de cabeça baixa"],
  fa_smile_presence_ratio: ["Smile presence", "Presença de sorriso"],
  fa_expressivity_index: ["Facial movement", "Movimento facial"],
  fa_expression_variety: ["Expression variety", "Variedade de expressão"],
  fa_congruence: ["Expression and content overlap", "Sobreposição expressão e conteúdo"],
  ep_too_soft_ratio: ["Too-soft share", "Trecho baixo demais"],
  ep_energy_trajectory: ["Energy trajectory", "Trajetória de energia"],
  ep_key_moment_lift: ["Lift at key moments", "Subida nos momentos-chave"],
  ep_confident_language: ["Direct language", "Linguagem direta"],
  ep_recovery: ["Recovery after a slip", "Recuperação após um deslize"],
  tm_pct_of_slot: ["Percent of slot", "Percentual do tempo"],
  tm_section_variance: ["Section timing variance", "Variação do tempo das seções"],
  tm_end_rush_events: ["End rushes", "Acelerações no fim"],
  tm_qa_time_protected: ["Q&A time protected", "Tempo de perguntas preservado"],
  qa_answer_first_ratio: ["Answer first", "Resposta primeiro"],
  qa_answer_length_s_median: ["Answer length", "Duração da resposta"],
  qa_structure_llm: ["Answer structure", "Estrutura da resposta"],
  qa_bridge_back_ratio: ["Bridge back", "Retorno ao tema"],
  qa_composure_llm: ["Answer composure", "Compostura na resposta"],
  sf_narration_alignment_ratio: ["Narration alignment", "Alinhamento da narração"],
  sf_narration_lead_s_median: ["Narration lead", "Antecedência da narração"],
  sf_clean_transition_ratio: ["Clean transitions", "Transições limpas"],
  sf_signpost_ratio: ["Screen signposts", "Sinalizações na tela"],
  sf_dead_air_per_10min: ["Dead air per 10 min", "Silêncio por 10 min"],
  sf_silent_demo_ratio: ["Silent demo", "Demonstração em silêncio"],
  sf_static_long_ratio: ["Long static screen", "Tela estática longa"],
  sf_rushed_ratio: ["Rushed screen changes", "Trocas de tela apressadas"],
  ocp_framing_score: ["Framing", "Enquadramento"],
  ocp_light_ok_ratio: ["Light", "Luz"],
  ocp_camera_visible_ratio: ["Camera visible", "Câmera visível"],
  ocp_reading_pattern_ratio: ["Reading pattern", "Padrão de leitura"],
  ocp_camera_stability: ["Camera stability", "Estabilidade da câmera"],
  ocp_toward_camera_ratio: ["Toward the camera", "De frente para a câmera"],
  oe_interaction_prompts_per_10min: ["Interaction prompts per 10 min", "Convites à interação por 10 min"],
  oe_direct_address_per_100w: ["Direct address per 100 words", "Endereçamento direto por 100 palavras"],
  oe_open_speech_start_s: ["Speech start", "Início da fala"],
  oe_open_30s_dead_air_s: ["Dead air in the open", "Silêncio na abertura"],
  oe_open_visual_change_s: ["First visual change", "Primeira mudança visual"],
  pq_snr_db: ["Signal to noise", "Sinal sobre ruído"],
  pq_integrated_lufs: ["Integrated loudness", "Volume integrado"],
  pq_clipping_ratio: ["Clipping", "Distorção por corte"],
  pq_frozen_video_s: ["Frozen video", "Vídeo congelado"],
  pq_true_peak_dbtp: ["True peak", "Pico real"],
};

const LUFS_FLOOR = -70;

export function metricLabel(id: string, locale: string): string {
  const pair = LABELS[id];
  if (!pair) return id.replaceAll("_", " ");
  return locale.toLowerCase().startsWith("pt") ? pair[1] : pair[0];
}

export function metricUnusable(id: string, value: number): boolean {
  return id === "pq_integrated_lufs" && value <= LUFS_FLOOR;
}

function trimNumber(value: number): string {
  if (!Number.isFinite(value)) return "";
  if (Number.isInteger(value)) return String(value);
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return value.toFixed(digits).replace(/\.?0+$/, "");
}

export function formatMeasured(value: number, unit: string | null | undefined): string {
  const u = (unit || "").trim();
  if (u === "ratio") return `${Math.round(value * 100)}%`;
  if (u === "LUFS") return `${trimNumber(value)} LUFS`;
  if (u === "dB" || u === "dBTP" || u === "dBFS") return `${trimNumber(value)} ${u}`;
  if (u === "s" || u === "seconds") return `${trimNumber(value)} s`;
  if (u === "llm_level") return trimNumber(value);
  if (u === "WPM" || u === "wpm") return `${Math.round(value)} WPM`;
  if (u === "per_minute" || u === "/min") return `${trimNumber(value)} /min`;
  if (u === "per_10min") return `${trimNumber(value)} /10 min`;
  if (!u || u === "count" || u === "score" || u === "level") return trimNumber(value);
  return `${trimNumber(value)} ${u}`;
}
