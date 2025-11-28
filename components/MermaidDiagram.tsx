'use client';

import { useEffect, useRef } from 'react';

type MermaidDiagramProps = {
  code: string;
};

export default function MermaidDiagram({ code }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const idRef = useRef<string>('mermaid-' + Math.random().toString(36).slice(2));

  useEffect(() => {
    let cancelled = false;

    async function renderDiagram() {
      if (!containerRef.current) return;

      const trimmed = code.trim();
      if (!trimmed) {
        containerRef.current.innerHTML = '';
        return;
      }

      try {
        const mermaid = (await import('mermaid')).default;

        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'default',
          flowchart: {
            useMaxWidth: false, // don't auto-shrink to container width
          },
          themeVariables: {
            fontSize: '16px', // bigger text & boxes
          },
        });

        console.log('[Mermaid] rendering diagram, length =', trimmed.length);

        const { svg, bindFunctions } = await mermaid.render(
          idRef.current,
          trimmed
        );

        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;

        // Make the SVG use more vertical space
        const svgEl = containerRef.current.querySelector('svg') as
          | SVGSVGElement
          | null;

        if (svgEl) {
          svgEl.removeAttribute('height'); // let it grow naturally
          svgEl.style.minHeight = '220px';
          svgEl.style.width = '100%';
        }

        if (bindFunctions) {
          bindFunctions(containerRef.current);
        }
      } catch (err) {
        console.error('[Mermaid] render error:', err);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML =
            '<div style="color:#fecaca;font-size:11px;">Failed to render Mermaid diagram.</div>';
        }
      }
    }

    if (containerRef.current) {
      containerRef.current.innerHTML = '';
    }
    renderDiagram();

    return () => {
      cancelled = true;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [code]);

  return (
    <div className="w-full overflow-x-auto bg-slate-900 rounded-xl px-4 py-6 min-h-[260px]">
      {/* Mermaid owns the innerHTML of this div */}
      <div ref={containerRef} className="inline-block" />
    </div>
  );
}
