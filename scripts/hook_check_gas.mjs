#!/usr/bin/env node
// Hook PostToolUse (.claude/settings.json): sửa gas/*.html xong thì tự chạy check_gas_client.mjs.
// exit 2 + stderr = báo lỗi ngược lại cho agent (gotcha #28 của playbook).
import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

let raw = "";
process.stdin.on("data", (d) => (raw += d)).on("end", () => {
  let file = "";
  try { file = (JSON.parse(raw).tool_input || {}).file_path || ""; } catch (e) { process.exit(0); }
  if (!/[\\/]gas[\\/][^\\/]+\.html$/.test(file)) process.exit(0);
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  try {
    execFileSync("node", [join(root, "scripts/check_gas_client.mjs")], { stdio: "pipe" });
  } catch (e) {
    process.stderr.write(String(e.stdout || "") + String(e.stderr || ""));
    process.exit(2);
  }
});
