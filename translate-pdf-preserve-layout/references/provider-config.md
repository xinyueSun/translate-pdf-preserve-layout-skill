# Translation service configuration

Read this file only when the default no-key service is unsuitable. PDFMathTranslate-next 2.9.x reads settings from environment variables prefixed with `PDF2ZH_`; command-line values override environment values.

## Recommended choices

- `siliconflowfree`: no API key; best for a quick default run. Document text is sent to a remote service.
- `google` or `bing`: no-key machine translation options; useful for straightforward prose.
- `openai`: OpenAI API or an endpoint using the OpenAI-specific settings.
- `openaicompatible`: any OpenAI-compatible endpoint.
- `ollama`: local Ollama server; useful when document text should remain local.
- `deepl`, `gemini`, `deepseek`, `qwenmt`, `azureopenai`, and others: use when the user already has the corresponding credentials.

## Environment examples

Set variables in the environment used to launch the wrapper. Do not echo their values.

```bash
export PDF2ZH_OPENAI_API_KEY='...'
export PDF2ZH_OPENAI_MODEL='gpt-4.1-mini'
export PDF2ZH_OPENAI_BASE_URL='https://api.openai.com/v1'
```

Then select `--engine openai`.

```bash
export PDF2ZH_OPENAI_COMPATIBLE_API_KEY='...'
export PDF2ZH_OPENAI_COMPATIBLE_MODEL='model-name'
export PDF2ZH_OPENAI_COMPATIBLE_BASE_URL='https://example.com/v1'
```

Then select `--engine openaicompatible`.

```bash
export PDF2ZH_OLLAMA_MODEL='qwen2.5:7b'
export PDF2ZH_OLLAMA_HOST='http://127.0.0.1:11434'
```

Then select `--engine ollama`.

Common credential names follow the upstream CLI field names: uppercase them, replace hyphens with underscores, and prefix `PDF2ZH_`. For example, `--deepl-auth-key` becomes `PDF2ZH_DEEPL_AUTH_KEY` and `--gemini-api-key` becomes `PDF2ZH_GEMINI_API_KEY`.

For `siliconflowfree`, leave wrapper JSON mode off. Testing on a 66-page structured research paper caused most grouped translations to fall back when JSON mode was requested. Automatic glossary extraction is also disabled by the wrapper unless `--auto-extract-glossary` is supplied.

## Advanced settings

Use wrapper options for common PDF behavior. For an upstream option not exposed by the wrapper, repeat `--pdf2zh-arg=...`, for example:

```bash
--pdf2zh-arg=--primary-font-family --pdf2zh-arg=sans-serif
```

Never pass an API-key option through `--pdf2zh-arg`; process arguments may be visible to other local users and can appear in logs.
