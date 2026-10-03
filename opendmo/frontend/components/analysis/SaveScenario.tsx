'use client';

import { useState } from 'react';
import { post, errMsg } from '@/lib/api';
import { useApp } from '@/lib/state';
import type { Run } from '@/lib/types';
import { Field, Modal } from '../ui';

export function SaveScenario({ run, onClose }: { run: Run; onClose: () => void }) {
  const { toast, bump } = useApp();
  const [name, setName] = useState(run.label || `${run.method_name} ${new Date().toISOString().slice(0, 10)}`);
  const [notes, setNotes] = useState('');
  const save = async () => {
    try {
      await post('/scenarios', { name, notes, run_id: run.id });
      toast('Scenario saved — compare it under Future & Economy › Scenarios', 'ok');
      bump();
      onClose();
    } catch (e) { toast(errMsg(e), 'error'); }
  };
  return (
    <Modal title="Save as scenario" onClose={onClose} footer={<><button className="btn ghost" onClick={onClose}>Cancel</button><button className="btn primary" onClick={save} disabled={!name.trim()}>Save</button></>}>
      <div className="stack">
        <Field label="Scenario name" htmlFor="scn-name"><input id="scn-name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
        <Field label="Notes (assumptions, source of parameters)" htmlFor="scn-notes"><textarea id="scn-notes" className="textarea" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <p className="tiny faint">Links to run {run.id}; the run itself stays immutable.</p>
      </div>
    </Modal>
  );
}
