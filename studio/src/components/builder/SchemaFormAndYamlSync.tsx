import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import {
  FileCode,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCw,
  Save,
  Loader2,
  Download,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { fetchScenarioRaw, validateScenario, saveAndGenerateScenario } from '../../services/api';

export const SchemaFormAndYamlSync: React.FC = () => {
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const appendLog = useStudioStore((s) => s.appendLog);

  const [yamlContent, setYamlContent] = useState<string>('');
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // Load raw YAML on scenario switch
  useEffect(() => {
    if (!currentScenario) return;
    const abortCtrl = new AbortController();
    fetchScenarioRaw(currentScenario.id, abortCtrl.signal)
      .then((raw) => {
        setYamlContent(raw.yaml);
        setValidationErrors([]);
        setIsValid(true);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        console.error('Failed to load raw YAML:', err);
      });

    return () => abortCtrl.abort();
  }, [currentScenario?.id]);

  const handleValidate = async () => {
    if (!yamlContent) return;
    setIsValidating(true);
    try {
      const res = await validateScenario({ yaml: yamlContent });
      setIsValid(res.valid);
      setValidationErrors(res.errors || []);
      if (res.valid) {
        appendLog(`[+] YAML Schema validation passed.`);
      } else {
        appendLog(`[!] YAML Schema validation failed with ${res.errors.length} errors.`);
      }
    } catch (err: unknown) {
      setIsValid(false);
      setValidationErrors([err instanceof Error ? err.message : String(err)]);
    } finally {
      setIsValidating(false);
    }
  };

  const handleSaveAndCompile = async () => {
    if (!currentScenario || !yamlContent) return;
    setIsSaving(true);
    appendLog(`[*] Saving YAML and auto-generating OMNeT++ / SUMO configs for '${currentScenario.id}'...`);
    try {
      const res = await saveAndGenerateScenario(currentScenario.id, yamlContent, undefined, true);
      appendLog(`[+] Scenario compiled successfully into '${res.output_directory}'. Generated: ${res.generated_files.join(', ')}`);
      setIsValid(true);
      setValidationErrors([]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`[!] Compilation error: ${msg}`);
      setValidationErrors([msg]);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-bg-panel select-none">
      {/* Action Toolbar */}
      <div className="h-10 bg-bg-card border-b border-border-subtle px-3 flex items-center justify-between font-mono text-xs shrink-0">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-brand-cyan" />
          <span className="font-bold text-slate-100">
            {currentScenario ? `${currentScenario.id}.yaml` : 'scenario.yaml'}
          </span>
          {isValid === true && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
              <CheckCircle2 className="w-3 h-3" /> SCHEMA VALID
            </span>
          )}
          {isValid === false && (
            <span className="flex items-center gap-1 text-[10px] text-accent-red font-bold bg-red-500/10 px-2 py-0.5 rounded border border-red-500/30">
              <AlertTriangle className="w-3 h-3" /> {validationErrors.length} ERRORS
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleValidate}
            disabled={isValidating}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-bg-panel border border-border-subtle hover:border-border-highlight text-slate-300 hover:text-white transition disabled:opacity-50"
          >
            {isValidating ? <Loader2 className="w-3 h-3 animate-spin text-brand-cyan" /> : <CheckCircle2 className="w-3 h-3 text-brand-cyan" />}
            <span>VALIDATE</span>
          </button>

          <button
            onClick={handleSaveAndCompile}
            disabled={isSaving || !currentScenario}
            className="flex items-center gap-1.5 px-3 py-1 rounded bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold transition shadow disabled:opacity-50"
          >
            {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>SAVE & COMPILE OMNET++</span>
          </button>
        </div>
      </div>

      {/* Validation Errors Box if any */}
      {validationErrors.length > 0 && (
        <div className="bg-red-950/40 border-b border-red-500/40 p-2 font-mono text-[11px] text-red-300 flex flex-col gap-1 max-h-24 overflow-y-auto shrink-0">
          {validationErrors.map((err, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-accent-red">•</span>
              <span>{err}</span>
            </div>
          ))}
        </div>
      )}

      {/* Monaco Code Editor */}
      <div className="flex-1 w-full overflow-hidden">
        <Editor
          height="100%"
          language="yaml"
          theme="vs-dark"
          value={yamlContent}
          onChange={(val) => {
            setYamlContent(val || '');
            setIsValid(null);
          }}
          options={{
            fontSize: 12,
            fontFamily: 'IBM Plex Mono, monospace',
            minimap: { enabled: false },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
          }}
        />
      </div>
    </div>
  );
};
