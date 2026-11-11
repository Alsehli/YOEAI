# YOEAI 3.0 built-in internet research — preparation only

Status: implemented and packaged for future qualification; NOT VERIFIED. No automated tests, sample queries, benchmarks, app launches, search-service launches, or installer validation were run for this change. Packaging compilation is separate from runtime testing.

## Conversation behavior

The existing local chat and selected local language model remain in charge. Startup registers the local assistant capability registry, including web.research, without opening a network connection, loading an embedding model, starting SearXNG, or performing a search. Ordinary chat already calls the unified assistant preparation route: the local model selects tools and resolves follow-ups; research generates bounded public queries, searches, reads HTTPS webpages, compares evidence, and passes cited findings into the local answer. Stable questions can remain local. No search mode or search button is introduced.

## Infrastructure

The default is bundled SearXNG using the existing supported Windows Python, SearXNG source, Waitress and YAML dependencies under SearchRuntime. The private service starts on demand on an ephemeral 127.0.0.1 port, authenticates host requests with a per-process token, rejects browser-origin requests, and stops after five idle minutes or app shutdown. Users need no Docker, API key or separate app.

Settings/web-research.json is automatically included in the common installer payload. It supports a managed HTTPS SearXNG-compatible endpoint as an alternative, but none is configured or required for the bundled path. Do not substitute random public instances. Remote searches and public website retrieval require internet access and available upstream engines. Model planning, evidence comparison, final inference, memories and documents remain local.

## Privacy and evidence

Public query generation receives the user's question and a bounded context made only from previous public query topics and public source titles. It does not receive document passages, approved memory contents, file scopes or private tool results. The registry prevents network calls after private evidence has entered a tool round without authorization. Outbound queries retain secret/path/email screening. Public page reads and managed endpoints require HTTPS, public DNS addresses, pinned destination IPs, TLS hostname validation, no cookies and bounded responses. Page text is untrusted data and cannot grant action permissions. Claims are compared by the local model using actual source URLs; that is not independent proof that every claim is true. Retrieved timestamps are not labeled verification timestamps. Inline research citation links not in the retrieved source registry are made non-clickable by the renderer. Search failure is reported while local chat can continue. The existing Stop action cancels research and the selected local-model work.

## Distribution and missing infrastructure

Both planned online and offline installers use the same prepared application payload, which includes the new lifecycle/reader modules, startup registration, citation renderer, Settings/web-research.json and the already bundled SearchRuntime. No research logic or cloud inference needs to be embedded in the bootstrap executable. Production installer/download flags remain disabled and no YOEAI 3.0 publication is claimed.

Static inventory found the bundled Python executable, SearXNG webapp source, Waitress and YAML directories. No additional hosting or new dependency download was needed for the selected local-service design. Compatibility of the new wrapper, upstream engine behavior, cancellation, citation rendering, latency, fresh installation and offline fallback remains unverified until testing is authorized. A managed HTTPS endpoint and its availability commitment would be missing if that alternative were selected.

The working installed app is not replaced or started by this preparation. The existing Lite foundation and user data are retained.
