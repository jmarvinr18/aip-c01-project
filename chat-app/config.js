// Clarvo web app configuration.
// Replace WS_URL with your API Gateway WebSocket endpoint (the wss:// URL from
// API Gateway → clarvo-ws → Stages → prod → "WebSocket URL").
//
// Format: wss://<api-id>.execute-api.ap-southeast-1.amazonaws.com/prod
window.CONFIG = {
  WS_URL: "wss://REPLACE_ME.execute-api.ap-southeast-1.amazonaws.com/prod"
};
