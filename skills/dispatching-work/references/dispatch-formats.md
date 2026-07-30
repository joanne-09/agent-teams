# Dispatch formats

`paste` prints the role/card token and obligation. `subagent` wraps the same
text as a one-deep agent prompt. `cron` renders a `claude -p` invocation. No
format performs the launch. Callers must distinguish rendered from launched.
