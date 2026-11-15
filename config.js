// Supabase 연결 정보. 비어 있으면 '로컬 테스트 모드'(서버 전송 없이 브라우저에만 저장)로 동작합니다.
// 아래 키는 공개 키(publishable/anon)이며, DB 보안은 RLS(INSERT 전용)가 담당합니다. service_role/secret 키는 절대 넣지 마십시오.
window.SURVEY_CONFIG = {
  SUPABASE_URL: "https://kdflmoittqbaelwokctp.supabase.co",
  SUPABASE_KEY: "sb_publishable_aizP8kEEFjQvqk3_qDJG_w_84OeE_Ss",
  TABLE: "responses",
  FORM_VERSION: "v4"
};
