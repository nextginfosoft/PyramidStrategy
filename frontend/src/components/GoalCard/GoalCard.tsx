import React, { useState } from 'react';
import clsx from 'clsx';

interface WealthMilestone {
  level: string;
  amount: string;
  targetYear?: string;
  isCompleted?: boolean;
  isActive?: boolean;
}

interface LifeGoal {
  id: number;
  title: string;
  priority: number;
  category: 'Asset' | 'Financial' | 'Lifestyle' | 'Travel' | 'Legacy';
  icon: string;
}

const WEALTH_LADDER: WealthMilestone[] = [
  { level: 'Level 1', amount: '₹25 Lakh', isCompleted: true },
  { level: 'Level 2', amount: '₹50 Lakh', isCompleted: true },
  { level: 'Level 3', amount: '₹1 Crore', isCompleted: true },
  { level: 'Level 4', amount: '₹10 Crore', isActive: true },
  { level: 'Level 5', amount: '₹50 Crore', targetYear: '2028' },
  { level: 'Target 1', amount: '₹100 Crore', targetYear: '2030' },
  { level: 'Target 2', amount: '₹1,000 Crore', targetYear: '2035' },
];

const LIFE_GOALS: LifeGoal[] = [
  { id: 1, title: 'Own a penthouse', priority: 1, category: 'Asset', icon: '🏢' },
  { id: 2, title: 'Pay ₹1 Crore in income tax within a year', priority: 1, category: 'Financial', icon: '💸' },
  { id: 3, title: 'Own a BMW', priority: 2, category: 'Lifestyle', icon: '🏎️' },
  { id: 4, title: 'Visit Dubai', priority: 3, category: 'Travel', icon: '✈️' },
  { id: 5, title: 'Travel across India', priority: 3, category: 'Travel', icon: '🗺️' },
  { id: 6, title: 'Visit Goa once every year', priority: 5, category: 'Travel', icon: '🏖️' },
  { id: 7, title: 'Take at least one international trip every year', priority: 6, category: 'Travel', icon: '🌍' },
  { id: 8, title: 'Visit the Statue of Liberty', priority: 7, category: 'Travel', icon: '🗽' },
  { id: 9, title: 'Own a farmhouse', priority: 8, category: 'Asset', icon: '🏡' },
  { id: 10, title: 'Start an NGO', priority: 9, category: 'Legacy', icon: '❤️' },
];

export const GoalCard: React.FC = () => {
  const [selectedFilter, setSelectedFilter] = useState<'ALL' | 'P1' | 'P2_P5' | 'P6_P9'>('ALL');

  const filteredGoals = LIFE_GOALS.filter((goal) => {
    if (selectedFilter === 'P1') return goal.priority === 1;
    if (selectedFilter === 'P2_P5') return goal.priority >= 2 && goal.priority <= 5;
    if (selectedFilter === 'P6_P9') return goal.priority >= 6;
    return true;
  });

  const getPriorityBadgeClass = (priority: number) => {
    if (priority === 1) return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
    if (priority <= 3) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    if (priority <= 6) return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-navy-700/50 bg-navy-900/60 backdrop-blur-md shadow-2xl relative overflow-hidden space-y-6">
      {/* Background Decorative Glow */}
      <div className="absolute -top-24 -right-24 w-60 h-60 bg-gradient-to-br from-amber-500/10 via-orange-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-60 h-60 bg-gradient-to-tr from-cyan-500/10 via-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-navy-800/80 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">🏆</span>
          <div>
            <h3 className="text-base font-extrabold text-white tracking-wide">
              Wealth Ladder & Vision Goals
            </h3>
            <p className="text-[11px] text-navy-400 font-medium">
              Milestone roadmap & life objectives tracker
            </p>
          </div>
        </div>
        <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30">
          Target: ₹10 Cr Focus
        </span>
      </div>

      {/* 1. Wealth Ladder Timeline Stepper */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs font-bold text-navy-300">
          <span>Wealth Ladder Milestones</span>
          <span className="text-[11px] text-cyan-400 font-mono">Active Level 4</span>
        </div>

        {/* Stepper Track Container */}
        <div className="relative pt-2 pb-1 overflow-x-auto no-scrollbar">
          <div className="flex items-start min-w-[650px] justify-between relative px-2">
            {/* Connecting Progress Line */}
            <div className="absolute top-5 left-6 right-6 h-1 bg-navy-800 rounded-full -z-0">
              <div className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-cyan-500 rounded-full w-[46%]" />
            </div>

            {WEALTH_LADDER.map((m, idx) => (
              <div
                key={idx}
                className="flex flex-col items-center text-center group cursor-pointer z-10 w-20"
              >
                {/* Node circle */}
                <div
                  className={clsx(
                    'w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300 border shadow-lg',
                    m.isCompleted && 'bg-emerald-500 text-navy-950 border-emerald-400 ring-2 ring-emerald-500/20',
                    m.isActive && 'bg-gradient-to-tr from-amber-400 to-orange-500 text-navy-950 border-amber-300 ring-4 ring-amber-500/30 animate-pulse scale-110',
                    !m.isCompleted && !m.isActive && 'bg-navy-900 text-navy-400 border-navy-700 hover:border-navy-500'
                  )}
                >
                  {m.isCompleted ? '✓' : m.isActive ? '★' : idx + 1}
                </div>

                {/* Level Title */}
                <span
                  className={clsx(
                    'text-[10px] font-bold mt-2 whitespace-nowrap',
                    m.isActive ? 'text-amber-400 font-extrabold' : m.isCompleted ? 'text-emerald-400' : 'text-navy-400'
                  )}
                >
                  {m.level}
                </span>

                {/* Target Amount */}
                <span
                  className={clsx(
                    'text-[11px] font-extrabold font-mono mt-0.5 whitespace-nowrap',
                    m.isActive ? 'text-white text-xs' : 'text-navy-200'
                  )}
                >
                  {m.amount}
                </span>

                {/* Target Year Tag */}
                {m.targetYear && (
                  <span className="text-[9px] text-navy-400 font-medium bg-navy-800/80 px-1.5 py-0.2 rounded mt-1 border border-navy-700">
                    {m.targetYear}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Life Goals Section */}
      <div className="space-y-3 pt-2 border-t border-navy-800/80">
        {/* Subheader & Filter Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-sm">🎯</span>
            <span className="text-xs font-extrabold text-white tracking-wide uppercase">
              Life Goals & Targets ({LIFE_GOALS.length})
            </span>
          </div>

          <div className="flex items-center gap-1 bg-navy-950/80 p-1 rounded-lg border border-navy-800">
            {(['ALL', 'P1', 'P2_P5', 'P6_P9'] as const).map((filterKey) => (
              <button
                key={filterKey}
                onClick={() => setSelectedFilter(filterKey)}
                className={clsx(
                  'px-2.5 py-0.5 rounded text-[10px] font-bold transition-all duration-150',
                  selectedFilter === filterKey
                    ? 'bg-amber-500 text-navy-950 shadow'
                    : 'text-navy-400 hover:text-white hover:bg-navy-800'
                )}
              >
                {filterKey === 'ALL' && 'All Goals'}
                {filterKey === 'P1' && '🔴 Top Priority'}
                {filterKey === 'P2_P5' && '🟠 Priority 2-5'}
                {filterKey === 'P6_P9' && '🟢 Priority 6-9'}
              </button>
            ))}
          </div>
        </div>

        {/* Goals Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5 pt-1">
          {filteredGoals.map((goal) => (
            <div
              key={goal.id}
              className="bg-navy-950/60 hover:bg-navy-800/60 border border-navy-800/90 hover:border-navy-700 rounded-xl p-3 flex flex-col justify-between transition-all duration-200 group hover:-translate-y-0.5 shadow-md"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xl p-1.5 bg-navy-900 rounded-lg border border-navy-800 group-hover:scale-110 transition-transform">
                  {goal.icon}
                </span>
                <span
                  className={clsx(
                    'text-[9px] font-extrabold px-2 py-0.5 rounded border uppercase tracking-wider font-mono',
                    getPriorityBadgeClass(goal.priority)
                  )}
                >
                  Priority #{goal.priority}
                </span>
              </div>

              <div className="mt-3">
                <p className="text-xs font-bold text-navy-100 group-hover:text-white leading-snug line-clamp-2">
                  {goal.title}
                </p>
                <span className="inline-block text-[9px] text-navy-400 font-semibold uppercase tracking-wider mt-1">
                  {goal.category}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
