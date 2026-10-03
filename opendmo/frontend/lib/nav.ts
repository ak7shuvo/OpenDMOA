import type { CoreId } from './types';

export interface NavCore { id: CoreId; num: string; name: string; route: string; chain: string[]; tabs: { id: string; name: string; roadmap?: boolean }[] }

/** Four fixed cores (CONTRACT.md §3, extended in v2). The Control Board lives under System. */
export const CORES: NavCore[] = [
  {
    id: 'observatory', num: '01', name: 'Destination Observatory', route: '/observatory/', chain: ['LOCATION', 'TIME', 'OBSERVATION'],
    tabs: [
      { id: 'visitor-flow', name: 'Visitor Flow & Crowding' },
      { id: 'capacity', name: 'Carrying Capacity' },
      { id: 'site', name: 'Site Condition' },
      { id: 'sentiment', name: 'Community Sentiment' },
      { id: 'heritage', name: 'Heritage Assets' },
    ],
  },
  {
    id: 'climate', num: '02', name: 'Climate & Risk', route: '/climate-risk/', chain: ['CHANGE', 'RISK'],
    tabs: [
      { id: 'weather', name: 'Weather Observations' },
      { id: 'hazards', name: 'Flood & Landslide' },
      { id: 'ecosystem', name: 'Ecosystem Stress' },
      { id: 'resilience', name: 'Resilience Command' },
    ],
  },
  {
    id: 'economy', num: '03', name: 'Future & Economy', route: '/future-economy/', chain: ['FORECAST', 'SCENARIO'],
    tabs: [
      { id: 'revenue', name: 'Revenue Signals' },
      { id: 'leakage', name: 'Leakage & Impact' },
      { id: 'forecast', name: 'Demand Forecast' },
      { id: 'scenarios', name: 'Scenarios' },
      { id: 'infrastructure', name: 'Infrastructure Pipeline' },
    ],
  },
  {
    id: 'lab', num: '04', name: 'Research & Policy Lab', route: '/research-lab/', chain: ['DECISION'],
    tabs: [
      { id: 'datasets', name: 'Dataset Explorer' },
      { id: 'methodology', name: 'Methodology Registry' },
      { id: 'models', name: 'Model Lab' },
      { id: 'runs', name: 'Run History' },
      { id: 'briefs', name: 'Policy Briefs' },
      { id: 'publications', name: 'Publication Queue' },
      { id: 'glossary', name: 'Glossary & Citation' },
      { id: 'vrar', name: 'VR/AR (roadmap)', roadmap: true },
    ],
  },
];

export const SYSTEM_TABS = [
  { id: 'overview', name: 'Overview' },
  { id: 'data', name: 'Demo & Data' },
  { id: 'destinations', name: 'Destinations' },
  { id: 'backup', name: 'Backup & Export' },
  { id: 'registry', name: 'Methods & Models' },
  { id: 'runs', name: 'Run History' },
  { id: 'audit', name: 'Audit Log' },
  { id: 'settings', name: 'Settings' },
  { id: 'diagnostics', name: 'Diagnostics' },
] as const;

export const CHAIN = ['LOCATION', 'TIME', 'OBSERVATION', 'CHANGE', 'RISK', 'FORECAST', 'SCENARIO', 'DECISION'];

/** Where each registered method is operated in the UI (used by search and the methodology registry). */
export function methodRoute(id: string): string {
  const rules: [RegExp, string][] = [
    [/^capacity\./, '/observatory/#capacity'], [/^(pressure|growth)\.|ratio\.(occupancy|visitor_density)/, '/observatory/#visitor-flow'],
    [/^site\.|ratio\.waste/, '/observatory/#site'], [/^sentiment\./, '/observatory/#sentiment'], [/^climate\./, '/climate-risk/#weather'],
    [/^hazard\./, '/climate-risk/#hazards'], [/^ecosystem\./, '/climate-risk/#ecosystem'], [/^resilience\./, '/climate-risk/#resilience'],
    [/^ratio\.revenue/, '/future-economy/#revenue'], [/^(economy|sustainability)\./, '/future-economy/#leakage'],
    [/^forecast\./, '/future-economy/#forecast'], [/^scenario\./, '/future-economy/#scenarios'],
  ];
  return rules.find(([rx]) => rx.test(id))?.[1] ?? '/research-lab/#methodology';
}
