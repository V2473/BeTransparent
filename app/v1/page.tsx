'use client';

import { useState, useCallback } from 'react';
import MermaidDiagram from '../../components/MermaidDiagram';

// API host + basic auth
const apiHost = process.env.API_HOST || process.env.NEXT_PUBLIC_API_HOST || '';
const username = process.env.USERNAME || process.env.NEXT_PUBLIC_USERNAME;
const password = process.env.PASSWORD || process.env.NEXT_PUBLIC_PASSWORD;
const auth =
  username && password ? 'Basic ' + btoa(username + ':' + password) : '';

// --- Types derived from Yana screen spec JSON ---

type ScreenAction = {
  label: string;
  navigates_to_screen_id?: string;
  navigates_to_step_slug?: string;
};

type ScreenComponent = {
  component_slug: string;
  label: string;
  placeholder?: string;
  role?: string;
  repeats?: string;
  binding?: string;
  actions?: ScreenAction[];
};

type ScreenSection = {
  type: string;
  title?: string;
  description?: string;
  components: ScreenComponent[];
};

type Screen = {
  screen_id: string;
  screen_type: string;
  title: string;
  subtitle?: string;
  functional_description: string;
  sections: ScreenSection[];
  primary_action?: ScreenAction;
  step_slugs?: string[];
  mermaid_node_ids?: string[];
};

type ScreenFlow = {
  flow_slug: string;
  name: string;
  description?: string;
  screens: string[];
};

// Evaluation & retrieval types
type EvaluationWorkflow = {
  workflow_id?: string;
  workflow_title?: string;
  estimated_clicks?: number;
  unusual_component_count?: number;
  unusual_components?: string[];
  design_system_alignment?: number;
  overall_score?: number;
  pros?: string[];
  cons?: string[];
};

type EvaluationResult = {
  workflows?: EvaluationWorkflow[];
  recommended_workflow_id?: string;
  recommendation_explanation?: string;
};

type VectorHit = {
  source_type: string; // 'DOC' | 'FLOW' | 'STEP' | 'COMP'
  code: string;
  name: string;
  similarity: number;
  content: string;
};

type YanaResult = {
  service: Record<string, unknown>;
  ui_graph: Record<string, unknown>;
  screen_flows: ScreenFlow[];
  screens: Screen[];
  global_mermaid: string;
  evaluation?: EvaluationResult;
  retrieval?: {
    vector_context_raw: string;
    vector_hits: VectorHit[];
  };
  debug?: {
    agent1_bundle: Record<string, unknown>;
    agent2_normalized: Record<string, unknown>;
  };
};

// --- UI components ---

function ScreenCard(props: {
  screen: Screen;
  isActive?: boolean;
  onClick?: () => void;
}) {
  const { screen, isActive, onClick } = props;

  return (
    <div
      onClick={onClick}
      className={`w-[360px] h-[640px] shrink-0 rounded-3xl borde... p-4 flex flex-col bg-[#E2ECF4] cursor-pointer transition-all ${
        isActive ? 'ring-2 ring-blue-500 shadow-lg' : 'shadow-sm'
      }`}
    >
      <header className="mb-3">
        <div className="text-[10px] uppercase tracking-wide text-slate-500">
          {screen.screen_type}
        </div>
        <h3 className="text-lg font-semibold text-slate-900">{screen.title}</h3>
        {screen.subtitle && (
          <p className="text-xs text-slate-700 mt-1">{screen.subtitle}</p>
        )}
      </header>

      <p className="text-[11px] text-slate-700 mb-3">
        {screen.functional_description}
      </p>

      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {screen.sections.map((section, idx) => (
          <section
            key={idx}
            className="bg-white rounded-2xl px-3 py-2.5 shadow-sm border border-slate-100"
          >
            {section.title && (
              <h4 className="text-xs font-semibold text-slate-900 mb-1.5">
                {section.title}
              </h4>
            )}
            {section.description && (
              <p className="text-[11px] text-slate-600 mb-2">
                {section.description}
              </p>
            )}
            <div className="space-y-1">
              {section.components.map((c, i) => (
                <div
                  key={i}
                  className="text-[11px] flex justify-between items-center"
                >
                  <span className="text-slate-800">{c.label}</span>
                  {c.role === 'primary' && (
                    <span className="px-2 py-0.5 text-[9px] rounded-xl bg-blue-600 text-white">
                      primary
                    </span>
                  )}
                  {c.role === 'secondary' && (
                    <span className="px-2 py-0.5 text-[9px] rounded-xl bg-slate-200 text-slate-700">
                      secondary
                    </span>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>

      {screen.primary_action?.label && (
        <button className="mt-3 w-full h-10 rounded-full bg-blue-600 text-white text-sm font-medium">
          {screen.primary_action.label}
        </button>
      )}
    </div>
  );
}

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [yanaResult, setYanaResult] = useState<YanaResult | null>(null);
  const [responseStatus, setResponseStatus] = useState<
    'not sent' | 'sent' | 'received' | 'error'
  >('not sent');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [activeFlowSlug, setActiveFlowSlug] = useState<string | null>(null);
  const [activeScreenId, setActiveScreenId] = useState<string | null>(null);

  const submitPrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) {
      return;
    }

    try {
      setResponseStatus('sent');
      setErrorMessage(null);

      const url = `${apiHost}/api/v1/search`;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(auth ? { Authorization: auth } : {}),
        },
        body: JSON.stringify({ query: prompt }),
      });

      if (!response.ok) {
        let errBody: Record<string, unknown> | null = null;
        try {
          errBody = await response.json();
        } catch {
          // ignore
        }
        setResponseStatus('error');
        setErrorMessage(
          (errBody && (errBody.error as string)) ||
            `Request failed with ${response.status}`
        );
        return;
      }

      const data: YanaResult = await response.json();
      setYanaResult(data);
      setResponseStatus('received');

      if (data.screen_flows && data.screen_flows.length > 0) {
        const firstFlow = data.screen_flows[0];
        setActiveFlowSlug(firstFlow.flow_slug);
        setActiveScreenId(firstFlow.screens[0] || null);
      }
    } catch (err) {
      console.error(err);
      setResponseStatus('error');
      setErrorMessage((err as Error).message || 'Unknown error');
    }
  };

  const getButtonColor = useCallback(() => {
    switch (responseStatus) {
      case 'not sent':
        return 'bg-slate-900 hover:bg-slate-800';
      case 'sent':
        return 'bg-amber-500';
      case 'received':
        return 'bg-emerald-600';
      case 'error':
        return 'bg-red-600';
      default:
        return 'bg-slate-900';
    }
  }, [responseStatus]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (responseStatus !== 'sent') {
        void submitPrompt(e as React.FormEvent);
      }
    }
  };

  const flows = yanaResult?.screen_flows || [];
  const screens = yanaResult?.screens || [];

  const activeFlow =
    flows.find((f) => f.flow_slug === activeFlowSlug) || flows[0] || null;

  const screensForFlow: Screen[] =
    activeFlow && yanaResult
      ? activeFlow.screens
          .map((id) => yanaResult.screens.find((s) => s.screen_id === id))
          .filter(Boolean) as Screen[]
      : [];

  const activeScreen =
    screensForFlow.find((s) => s.screen_id === activeScreenId) ||
    screens.find((s) => s.screen_id === activeScreenId) ||
    screensForFlow[0] ||
    null;

  const uiGraph = yanaResult?.ui_graph || {};
  const graphNodes: Record<string, unknown>[] =
    (uiGraph.nodes as Record<string, unknown>[]) || [];
  const graphComponents: Record<string, unknown>[] =
    (uiGraph.ui_components as Record<string, unknown>[]) || [];

  const nodesByStepSlug = new Map<string, Record<string, unknown>>();
  graphNodes.forEach((n: Record<string, unknown>) => {
    if (n.step_slug) {
      nodesByStepSlug.set(n.step_slug as string, n);
    }
  });

  const dsByKey = new Map<string, Record<string, unknown>>();
  graphComponents.forEach((c: Record<string, unknown>) => {
    const key = (c.slug || c.key) as string;
    if (key) {
      dsByKey.set(key, c);
    }
  });

  const flowByScreenId = new Map<string, string>();
  (yanaResult?.screen_flows || []).forEach((flow) => {
    flow.screens.forEach((sid: string) =>
      flowByScreenId.set(sid, flow.flow_slug)
    );
  });

  const evalByFlowId = new Map<string, Record<string, unknown>>();
  (
    yanaResult?.evaluation?.workflows as Record<string, unknown>[]
  )?.forEach((w: Record<string, unknown>) => {
    if (w.workflow_id) {
      evalByFlowId.set(w.workflow_id as string, w);
    }
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 bg-[linear-gradient(340deg,#e6f4d2_1%,#a7cbe3_62%)]">
        <div className="mx-auto max-w-6xl px-4 py-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold">
              YanaAI - workflow generator
            </h1>
            <p className="mt-1 text-sm text-slate-700 max-w-xl">
              Вставте BRD, запустіть pipeline і подивіться на згенеровані
              потоки та екрани в стилі Дії.
            </p>
            <p className="mt-1 text-xs text-slate-600">
              Tip:{' '}
              <kbd className="px-1.5 py-0.5 rounded bg-slate-900 text-white text-[10px]">
                Cmd/Ctrl + Enter
              </kbd>{' '}
              to send.
            </p>
          </div>
          <a
            href="https://yana-diia-v3.vercel.app/lego?service=kotyk"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
          >
            Конструктор Lego
          </a>
          <div className="hidden md:flex flex-col items-end text-xs text-slate-700">
            <span className="font-mono">
              API_HOST: {apiHost || '<same origin>'}
            </span>
            <span>Status: {responseStatus}</span>
          </div>
        </div>
      </div>

      {/* Prompt form */}
      <div className="mx-auto max-w-6xl px-4 mt-5">
        <form
          onSubmit={submitPrompt}
          className="rounded-2xl border border-slate-200 bg-white p-4 flex flex-col gap-3 shadow-sm"
        >
          <label className="text-sm font-medium mb-1">BRD description</label>
          <textarea
            rows={4}
            className="w-full rounded-xl border border-slate...us:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
            value={prompt}
            placeholder="Наприклад: онлайн заняття спортом в додатку..."
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <div className="flex items-center justify-between gap-3 mt-1">
            {errorMessage && (
              <div className="text-xs text-red-600 max-w-sm">{errorMessage}</div>
            )}
            <button
              type="submit"
              className={`ml-auto inline-flex items-center g...m font-medium text-white transition-colors ${getButtonColor()}`}
              disabled={responseStatus === 'sent'}
            >
              {responseStatus === 'sent' ? 'Generating…' : 'Generate workflow'}
            </button>
          </div>
        </form>
      </div>

      {/* Main content */}
      <div className="mx-auto max-w-6xl px-4 mt-6 mb-10 space-y-6">
        {!yanaResult && (
          <div className="text-sm text-slate-600">
            No workflow generated yet. Paste a BRD above and click{' '}
            <span className="font-semibold">Generate workflow</span>.
          </div>
        )}

        {yanaResult && (
          <>
            {/* Flow tabs */}
            <div>
              <h2 className="text-sm font-semibold mb-2">
                Candidate workflows
              </h2>
              <div className="flex flex-wrap gap-2">
                {flows.map((flow) => (
                  <button
                    key={flow.flow_slug}
                    type="button"
                    onClick={() => {
                      setActiveFlowSlug(flow.flow_slug);
                      setActiveScreenId(flow.screens[0] || null);
                    }}
                    className={`px-3 py-1.5 rounded-full text-xs border ${
                      activeFlow && activeFlow.flow_slug === flow.flow_slug
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-800 border-slate-200'
                    }`}
                  >
                    {flow.name}{' '}
                    <span className="opacity-70">
                      ({flow.screens.length})
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Screens row */}
            {screensForFlow.length > 0 && (
              <div>
                <h2 className="text-sm font-semibold mb-2">
                  Screens in flow: {activeFlow?.name}
                </h2>
                <div className="flex gap-4 overflow-x-auto pb-3">
                  {screensForFlow.map((screen) => (
                    <ScreenCard
                      key={screen.screen_id}
                      screen={screen}
                      isActive={screen.screen_id === activeScreenId}
                      onClick={() => setActiveScreenId(screen.screen_id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Active screen details + inspector */}
            {activeScreen && (
              <>
                {/* 1. Screen details + Global Mermaid */}
                <div className="grid grid-cols-1 md:grid-cols-[2fr,1fr] gap-4 mt-4">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <h3 className="text-sm font-semibold mb-1">Screen details</h3>
                    <p className="text-xs text-slate-600 mb-3">
                      ID:{' '}
                      <code className="font-mono">
                        {activeScreen.screen_id}
                      </code>{' '}
                      · type:{' '}
                      <code className="font-mono">
                        {activeScreen.screen_type}
                      </code>
                    </p>
                    <ul className="text-xs text-slate-700 space-y-1">
                      {activeScreen.step_slugs &&
                        activeScreen.step_slugs.length > 0 && (
                          <li>
                            <span className="font-semibold">Steps:</span>{' '}
                            {activeScreen.step_slugs.join(', ')}
                          </li>
                        )}
                      {activeScreen.mermaid_node_ids &&
                        activeScreen.mermaid_node_ids.length > 0 && (
                          <li>
                            <span className="font-semibold">
                              Mermaid nodes:
                            </span>{' '}
                            {activeScreen.mermaid_node_ids.join(', ')}
                          </li>
                        )}
                    </ul>
                  </div>

                  {yanaResult && (
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <h3 className="text-sm font-semibold mb-1">
                        Global Mermaid
                      </h3>
                      <p className="text-[11px] text-slate-600 mb-2">
                        This is the merged workflow graph generated by Yana.
                        Nodes correspond to steps; edges are transitions.
                      </p>
                      <MermaidDiagram code={yanaResult.global_mermaid} />
                      <details className="mt-2 text-[10px] text-slate-500">
                        <summary className="cursor-pointer">
                          Show raw mermaid code
                        </summary>
                        <pre className="mt-1 whitespace-pre-wrap bg-slate-900 text-slate-50 rounded-lg p-2 max-h-40 overflow-auto">
                          {yanaResult.global_mermaid}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>

                {/* 2. Why this screen + Design system components */}
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Why this screen */}
                  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <h3 className="text-sm font-semibold mb-1">
                      Why this screen
                    </h3>
                    <p className="text-[11px] text-slate-600 mb-2">
                      Steps and UI components that led to this screen, based on
                      normalized workflow graph.
                    </p>
                    <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
                      {(activeScreen.step_slugs || []).map((slug) => {
                        const node = nodesByStepSlug.get(slug);
                        if (!node) return null;
                        const comps = (node.components || []) as Record<
                          string,
                          unknown
                        >[];
                        return (
                          <div
                            key={slug}
                            className="border border-slate-100 rounded-xl p-2.5 bg-slate-50"
                          >
                            <div className="text-[11px] font-mono text-slate-500 mb-0.5">
                              {slug}
                            </div>
                            <div className="text-xs font-semibold text-slate-900">
                              {(node.title as string) || (node.step_slug as string)}
                            </div>
                            {(node.description as string) && (
                              <p className="text-[11px] text-slate-600 mt-1 whitespace-pre-wrap">
                                {node.description as string}
                              </p>
                            )}
                            {comps.length > 0 && (
                              <div className="mt-1">
                                <div className="text-[10px] font-semibold text-slate-700 mb-0.5">
                                  Components on this step
                                </div>
                                <ul className="space-y-0.5">
                                  {comps.map((c, idx) => (
                                    <li
                                      key={idx}
                                      className="flex items-center justify-between text-[11px]"
                                    >
                                      <span className="font-mono text-slate-700">
                                        {c.key as string}
                                      </span>
                                      <span className="ml-2 text-slate-600 flex-1 truncate">
                                        {(c.name as string) ||
                                          (c.description as string)}
                                      </span>
                                      {(c.role as string) && (
                                        <span className="ml-2 px-1.5 py-0.5 rounded-full text-[9px] bg-slate-200 text-slate-700">
                                          {c.role as string}
                                        </span>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Design system components */}
                  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <h3 className="text-sm font-semibold mb-1">
                      Components from design system
                    </h3>
                    <p className="text-[11px] text-slate-600 mb-2">
                      For every component slug used on this screen, show
                      official description.
                    </p>
                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                      {Array.from(
                        new Set(
                          activeScreen.sections.flatMap((sec) =>
                            sec.components.map((c) => c.component_slug)
                          )
                        )
                      ).map((slug) => {
                        const comp = dsByKey.get(slug);
                        return (
                          <div
                            key={slug}
                            className="border border-slate-100 rounded-xl p-2.5 bg-slate-50"
                          >
                            <div className="text-[11px] font-mono text-slate-500">
                              {slug}
                            </div>
                            <div className="text-xs font-semibold text-slate-900">
                              {(comp?.name as string) ||
                                (comp?.type as string) ||
                                'Unknown component'}
                            </div>
                            {comp && (comp.description as string) && (
                              <p className="text-[11px] text-slate-600 mt-1">
                                {comp.description as string}
                              </p>
                            )}
                            {comp && (comp.usage_notes as string) && (
                              <p className="text-[10px] text-slate-500 mt-1">
                                <span className="font-semibold">Usage:</span>{' '}
                                {comp.usage_notes as string}
                              </p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* 3. Flow evaluation + similarity evidence */}
                {yanaResult?.evaluation && (
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Flow evaluation */}
                    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                      <h3 className="text-sm font-semibold mb-2">
                        Flow evaluation
                      </h3>
                      {(() => {
                        const flowSlug = flowByScreenId.get(
                          activeScreen.screen_id
                        );
                        if (!flowSlug) {
                          return (
                            <p className="text-[11px] text-slate-500">
                              This screen is not mapped to any screen_flow.
                            </p>
                          );
                        }
                        const evalRow =
                          evalByFlowId.get(flowSlug) ||
                          (yanaResult.evaluation!.workflows || []).find(
                            (w: Record<string, unknown>) =>
                              w.workflow_id === flowSlug ||
                              w.workflow_title === activeFlow?.name
                          );
                        if (!evalRow) {
                          return (
                            <p className="text-[11px] text-slate-500">
                              No evaluation found for flow{' '}
                              <code className="font-mono">{flowSlug}</code>.
                            </p>
                          );
                        }
                        const isRecommended =
                          yanaResult.evaluation!.recommended_workflow_id ===
                          flowSlug;
                        return (
                          <div className="space-y-2 text-[11px]">
                            <div className="flex items-center justify-between">
                              <div className="font-semibold">
                                {activeFlow?.name || (evalRow.workflow_title as string)}
                              </div>
                              {isRecommended && (
                                <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px]">
                                  Recommended
                                </span>
                              )}
                            </div>
                            <div className="grid grid-cols-2 gap-1">
                              {typeof evalRow.estimated_clicks === 'number' && (
                                <div>
                                  <div className="text-slate-500">
                                    Main path clicks
                                  </div>
                                  <div className="font-semibold">
                                    {evalRow.estimated_clicks.toFixed(0)}
                                  </div>
                                </div>
                              )}
                              {typeof evalRow.design_system_alignment ===
                                'number' && (
                                <div>
                                  <div className="text-slate-500">
                                    Design alignment
                                  </div>
                                  <div className="font-semibold">
                                    {(
                                      evalRow.design_system_alignment * 100
                                    ).toFixed(0)}
                                    %
                                  </div>
                                </div>
                              )}
                              {typeof evalRow.overall_score === 'number' && (
                                <div>
                                  <div className="text-slate-500">
                                    Overall score
                                  </div>
                                  <div className="font-semibold">
                                    {(evalRow.overall_score * 100).toFixed(0)}%
                                  </div>
                                </div>
                              )}
                              {typeof evalRow.unusual_component_count ===
                                'number' && (
                                <div>
                                  <div className="text-slate-500">
                                    Unusual components
                                  </div>
                                  <div className="font-semibold">
                                    {evalRow.unusual_component_count}
                                  </div>
                                </div>
                              )}
                            </div>
                            {Array.isArray(evalRow.pros) &&
                              evalRow.pros.length > 0 && (
                                <div>
                                  <div className="text-slate-500 mb-0.5">
                                    Pros
                                  </div>
                                  <ul className="list-disc pl-4">
                                    {evalRow.pros.map(
                                      (p: string, i: number) => (
                                        <li key={i}>{p}</li>
                                      )
                                    )}
                                  </ul>
                                </div>
                              )}
                            {Array.isArray(evalRow.cons) &&
                              evalRow.cons.length > 0 && (
                                <div>
                                  <div className="text-slate-500 mb-0.5">
                                    Cons
                                  </div>
                                  <ul className="list-disc pl-4">
                                    {evalRow.cons.map(
                                      (c: string, i: number) => (
                                        <li key={i}>{c}</li>
                                      )
                                    )}
                                  </ul>
                                </div>
                              )}
                          </div>
                        );
                      })()}
                    </div>

                    {/* Cosine similarity hits */}
                    {yanaResult.retrieval?.vector_hits && (
                      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                        <h3 className="text-sm font-semibold mb-2">
                          Similar flows & components
                        </h3>
                        <p className="text-[11px] text-slate-600 mb-2">
                          Top matches from Diia reference flows and UI
                          components (cosine similarity).
                        </p>
                        <div className="space-y-1 max-h-64 overflow-y-auto pr-1">
                          {yanaResult.retrieval.vector_hits
                            .filter(
                              (h) =>
                                h.source_type === 'FLOW' ||
                                h.source_type === 'COMP'
                            )
                            .slice(0, 8)
                            .map((h, idx) => (
                              <div
                                key={idx}
                                className="flex items-start justify-between text-[10px]"
                              >
                                <div className="mr-2">
                                  <div className="font-mono text-slate-600">
                                    [{h.source_type}] {h.code}
                                  </div>
                                  <div className="text-slate-800 truncate">
                                    {h.name}
                                  </div>
                                </div>
                                <div className="text-right">
                                  <div className="font-semibold">
                                    {(h.similarity * 100).toFixed(1)}%
                                  </div>
                                  <div className="text-slate-500">cos sim</div>
                                </div>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. Debug JSON (optional) */}
                {yanaResult?.debug && (
                  <details className="mt-4 rounded-2xl border border-slate-200 bg-white p-3 text-[11px]">
                    <summary className="cursor-pointer font-semibold">
                      Debug JSON (agents 1–3)
                    </summary>
                    <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
                      <div>
                        <div className="font-semibold mb-1">
                          Agent 1 – candidate bundle
                        </div>
                        <pre className="bg-slate-900 text-slate-50 rounded-lg p-2 whitespace-pre-wrap text-[10px]">
                          {JSON.stringify(
                            yanaResult.debug.agent1_bundle,
                            null,
                            2
                          )}
                        </pre>
                      </div>
                      <div>
                        <div className="font-semibold mb-1">
                          Agent 2 – normalized bundle
                        </div>
                        <pre className="bg-slate-900 text-slate-50 rounded-lg p-2 whitespace-pre-wrap text-[10px]">
                          {JSON.stringify(
                            yanaResult.debug.agent2_normalized,
                            null,
                            2
                          )}
                        </pre>
                      </div>
                      {yanaResult.evaluation && (
                        <div>
                          <div className="font-semibold mb-1">
                            Agent 3 – evaluation
                          </div>
                          <pre className="bg-slate-900 text-slate-50 rounded-lg p-2 whitespace-pre-wrap text-[10px]">
                            {JSON.stringify(yanaResult.evaluation, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </details>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}