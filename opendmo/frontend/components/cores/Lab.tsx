'use client';

import { EntityTable } from '../registers/EntityTable';
import { CoreFrame } from './CoreFrame';
import { BriefBuilder, DatasetExplorer, GlossaryCitation, MethodologyRegistry, ModelLab, RunHistory, VrArRoadmap } from './LabParts';

export function LabCore() {
  return (
    <CoreFrame core="lab"
      lede="From evidence to decision: explore and version datasets, inspect every method, run models safely, trace every result and turn selected runs into citable policy briefs."
      render={(tab) => {
        switch (tab) {
          case 'methodology': return <MethodologyRegistry />;
          case 'models': return <ModelLab />;
          case 'runs': return <RunHistory />;
          case 'briefs': return <BriefBuilder />;
          case 'publications':
            return (
              <EntityTable entity="publications" title="Publication queue" scoped={false} sub="idea → draft → review → submitted → published"
                fields={[
                  { key: 'title', label: 'Title', required: true, wrap: true },
                  { key: 'authors', label: 'Authors', wrap: true },
                  { key: 'pub_type', label: 'Type', type: 'select', options: ['policy-brief', 'working-paper', 'journal-article', 'conference', 'dataset', 'report'] },
                  { key: 'status', label: 'Status', type: 'select', options: ['idea', 'draft', 'review', 'submitted', 'published'],
                    status: { idea: 'watch', draft: 'watch', review: 'watch', submitted: 'ok', published: 'ok' } },
                  { key: 'venue', label: 'Venue' },
                  { key: 'due', label: 'Due', type: 'date' },
                  { key: 'brief_id', label: 'Linked brief id', inTable: false },
                  { key: 'notes', label: 'Notes', type: 'textarea', inTable: false },
                ]} />
            );
          case 'glossary': return <GlossaryCitation />;
          case 'vrar': return <VrArRoadmap />;
          default: return <DatasetExplorer />;
        }
      }} />
  );
}
