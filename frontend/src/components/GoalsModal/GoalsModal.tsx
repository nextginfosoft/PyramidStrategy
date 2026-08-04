import React, { useState } from 'react';
import clsx from 'clsx';

interface GoalsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

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
  { level: 'Level 1', amount: '₹25 Lakh', isActive: true },
  { level: 'Level 2', amount: '₹50 Lakh' },
  { level: 'Level 3', amount: '₹1 Crore' },
  { level: 'Level 4', amount: '₹10 Crore' },
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

export const GoalsModal: React.FC<GoalsModalProps> = ({ isOpen, onClose }) => {
  const [selectedFilter, setSelectedFilter] = useState<'ALL' | 'P1' | 'P2_P5' | 'P6_P9'>('ALL');
  const [activeTab, setActiveTab] = useState<'LADDER' | 'GOALS'>('GOALS');
  const [activeLevelIndex, setActiveLevelIndex] = useState<number>(0);

  if (!isOpen) return null;

  const currentMilestone = WEALTH_LADDER[activeLevelIndex] || WEALTH_LADDER[0];
  const nextMilestone = WEALTH_LADDER[activeLevelIndex + 1];

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

  // Dynamic progress line percentage
  const progressPct = ((activeLevelIndex + 0.5) / WEALTH_LADDER.length) * 100;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/80 backdrop-blur-md p-4 overflow-y-auto animate-fade-in">
      <div className="bg-navy-900 border border-navy-700/80 rounded-2xl w-full max-w-5xl overflow-hidden shadow-2xl relative flex flex-col max-h-[90vh]">
        {/* Background glow effects */}
        <div className="absolute -top-32 -right-32 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -left-32 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-navy-800 flex items-center justify-between bg-navy-950/60 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <span className="text-xl">🏆</span>
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide">
                Wealth Ladder & Life Objectives
              </h2>
              <p className="text-xs text-navy-400">
                Click any milestone on the timeline to set your current active focus level
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* View Switcher Tabs */}
            <div className="flex items-center bg-navy-900 border border-navy-800 p-1 rounded-xl">
              <button
                onClick={() => setActiveTab('GOALS')}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs font-bold transition-all',
                  activeTab === 'GOALS'
                    ? 'bg-amber-500 text-navy-950 shadow-md'
                    : 'text-navy-300 hover:text-white'
                )}
              >
                🎯 Life Goals (10)
              </button>
              <button
                onClick={() => setActiveTab('LADDER')}
                className={clsx(
                  'px-3 py-1.5 rounded-lg text-xs font-bold transition-all',
                  activeTab === 'LADDER'
                    ? 'bg-amber-500 text-navy-950 shadow-md'
                    : 'text-navy-300 hover:text-white'
                )}
              >
                👑 Wealth Ladder
              </button>
            </div>

            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-navy-800 hover:bg-navy-700 text-navy-300 hover:text-white flex items-center justify-center transition border border-navy-700"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* Active Target Banner */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-amber-950/40 via-navy-900 to-navy-950 border border-amber-500/30 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl animate-bounce">🔥</span>
              <div>
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-amber-400">
                  Current Target Focus (User Movable)
                </span>
                <h4 className="text-sm font-extrabold text-white">
                  {currentMilestone.level}: {currentMilestone.amount} Milestone
                </h4>
              </div>
            </div>

            <div className="text-right">
              <span className="text-xs text-navy-400 font-medium block">Next Milestone</span>
              <span className="text-xs font-bold text-cyan-400 font-mono">
                {nextMilestone ? `${nextMilestone.level}: ${nextMilestone.amount}` : 'Top Target Reached! 🚀'}
              </span>
            </div>
          </div>

          {activeTab === 'LADDER' || activeTab === 'GOALS' ? (
            <>
              {/* 1. Wealth Ladder Section */}
              <div className="space-y-3 bg-navy-950/40 border border-navy-800/80 rounded-xl p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-extrabold text-navy-200 uppercase tracking-wider flex items-center gap-2">
                    <span>👑</span> Wealth Ladder Timeline
                  </h3>
                  <span className="text-xs text-amber-400 font-mono font-bold">
                    Active Target: {currentMilestone.level} ({currentMilestone.amount})
                  </span>
                </div>

                <div className="relative pt-3 pb-2 overflow-x-auto">
                  <div className="flex items-start min-w-[700px] justify-between relative px-4">
                    {/* Progress Bar Line */}
                    <div className="absolute top-6 left-8 right-8 h-1.5 bg-navy-800 rounded-full -z-0">
                      <div
                        className="h-full bg-gradient-to-r from-emerald-500 via-amber-400 to-cyan-500 rounded-full transition-all duration-500"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>

                    {WEALTH_LADDER.map((m, idx) => {
                      const isCompleted = idx < activeLevelIndex;
                      const isActive = idx === activeLevelIndex;

                      return (
                        <div
                          key={idx}
                          onClick={() => setActiveLevelIndex(idx)}
                          title={`Click to set ${m.level} (${m.amount}) as active focus`}
                          className="flex flex-col items-center text-center group cursor-pointer z-10 w-24 active:scale-95 transition-transform"
                        >
                          <div
                            className={clsx(
                              'w-8 h-8 rounded-full flex items-center justify-center text-xs font-extrabold transition-all duration-300 border shadow-lg',
                              isCompleted && 'bg-emerald-500 text-navy-950 border-emerald-400 ring-2 ring-emerald-500/20',
                              isActive && 'bg-gradient-to-tr from-amber-400 to-orange-500 text-navy-950 border-amber-300 ring-4 ring-amber-500/30 scale-125 shadow-amber-500/50',
                              !isCompleted && !isActive && 'bg-navy-900 text-navy-400 border-navy-700 hover:border-amber-500/50 hover:text-white'
                            )}
                          >
                            {isCompleted ? '✓' : isActive ? '★' : idx + 1}
                          </div>

                          <span
                            className={clsx(
                              'text-xs font-bold mt-2 whitespace-nowrap transition-colors',
                              isActive ? 'text-amber-400 font-extrabold' : isCompleted ? 'text-emerald-400' : 'text-navy-400 group-hover:text-navy-200'
                            )}
                          >
                            {m.level}
                          </span>

                          <span
                            className={clsx(
                              'text-xs font-extrabold font-mono mt-0.5 whitespace-nowrap transition-colors',
                              isActive ? 'text-white text-sm font-black' : 'text-navy-200'
                            )}
                          >
                            {m.amount}
                          </span>

                          {m.targetYear && (
                            <span className="text-[10px] text-navy-400 font-semibold bg-navy-800/80 px-2 py-0.5 rounded mt-1.5 border border-navy-700">
                              {m.targetYear}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* 2. Life Goals Section */}
              <div className="space-y-4 pt-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🎯</span>
                    <h3 className="text-sm font-extrabold text-white tracking-wide uppercase">
                      Life Objectives & Priorities ({LIFE_GOALS.length})
                    </h3>
                  </div>

                  {/* Filter Pills */}
                  <div className="flex items-center gap-1.5 bg-navy-950 p-1.5 rounded-xl border border-navy-800">
                    {(['ALL', 'P1', 'P2_P5', 'P6_P9'] as const).map((filterKey) => (
                      <button
                        key={filterKey}
                        onClick={() => setSelectedFilter(filterKey)}
                        className={clsx(
                          'px-3 py-1 rounded-lg text-xs font-bold transition-all',
                          selectedFilter === filterKey
                            ? 'bg-amber-500 text-navy-950 shadow-md'
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
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredGoals.map((goal) => (
                    <div
                      key={goal.id}
                      className="bg-navy-950/70 hover:bg-navy-850/70 border border-navy-800/90 hover:border-navy-700 rounded-xl p-4 flex flex-col justify-between transition-all duration-200 group shadow-md"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <span className="text-2xl p-2 bg-navy-900 rounded-xl border border-navy-800 group-hover:scale-110 transition-transform">
                            {goal.icon}
                          </span>
                          <div>
                            <span className="text-[10px] text-navy-400 font-bold uppercase tracking-wider block">
                              {goal.category}
                            </span>
                            <span
                              className={clsx(
                                'text-[10px] font-extrabold px-2 py-0.5 rounded border uppercase tracking-wider font-mono inline-block mt-0.5',
                                getPriorityBadgeClass(goal.priority)
                              )}
                            >
                              Priority #{goal.priority}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-3 pt-3 border-t border-navy-850">
                        <p className="text-sm font-extrabold text-navy-100 group-hover:text-white leading-snug">
                          {goal.title}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-navy-800 bg-navy-950/60 flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-navy-800 hover:bg-navy-700 text-white font-bold rounded-xl text-xs transition border border-navy-700"
          >
            Close Goals Window
          </button>
        </div>
      </div>
    </div>
  );
};
