import React, { useState, useEffect, useRef } from 'react';
import { Crosshair, Layers, Cpu, ExternalLink, Menu, X, MapPin, SlidersHorizontal, GitCompare } from 'lucide-react';

export type ActiveView = 'sentinel' | 'spatial' | 'multi-location' | 'disagreement' | 'batch' | 'models';

interface NavigationProps {
  view: ActiveView;
  setView: (view: ActiveView) => void;
}

export const Navigation: React.FC<NavigationProps> = ({ view, setView }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent | TouchEvent) {
      if (navRef.current && !navRef.current.contains(event.target as Node)) {
        setMobileMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, []);

  const handleSelectView = (newView: ActiveView) => {
    setView(newView);
    setMobileMenuOpen(false);
  };

  return (
    <nav className="dropdown-nav" ref={navRef} aria-label="Main Navigation">
      {/* Mobile Menu Toggle Button */}
      <div className="mobile-nav-header">
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle Navigation Menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          <span>Menu</span>
        </button>
        <span className="mobile-current-view">
          {view === 'sentinel'
            ? 'Reliability Sentinel'
            : view === 'spatial'
            ? 'Spatial Reliability'
            : view === 'multi-location'
            ? 'Multi-Location Intelligence'
            : view === 'disagreement'
            ? 'Forecast Disagreement'
            : view === 'batch'
            ? 'Batch Evaluation'
            : 'Model Registry'}
        </span>
      </div>

      {/* Nav Items Container */}
      <div className={`nav-items-container ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        {/* Reliability Sentinel Direct Button */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'sentinel' ? 'active' : ''}
            onClick={() => handleSelectView('sentinel')}
          >
            <Crosshair size={16} /> Reliability Sentinel
          </button>
        </div>

        {/* Spatial Reliability Intelligence Direct Button */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'spatial' ? 'active' : ''}
            onClick={() => handleSelectView('spatial')}
          >
            <MapPin size={16} /> Spatial Reliability
            <span
              style={{
                marginLeft: '6px',
                background: '#0ea5e9',
                color: '#ffffff',
                padding: '2px 7px',
                borderRadius: '10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                letterSpacing: '0.02em',
              }}
            >
              Day 27
            </span>
          </button>
        </div>

        {/* Multi-Location Intelligence Direct Button (Day 28) */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'multi-location' ? 'active' : ''}
            onClick={() => handleSelectView('multi-location')}
          >
            <SlidersHorizontal size={16} /> Multi-Location Intelligence
            <span
              style={{
                marginLeft: '6px',
                background: '#8b5cf6',
                color: '#ffffff',
                padding: '2px 7px',
                borderRadius: '10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                letterSpacing: '0.02em',
              }}
            >
              Day 28
            </span>
          </button>
        </div>

        {/* Forecast Disagreement Intelligence Direct Button (Day 29) */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'disagreement' ? 'active' : ''}
            onClick={() => handleSelectView('disagreement')}
          >
            <GitCompare size={16} /> Forecast Disagreement
            <span
              style={{
                marginLeft: '6px',
                background: '#6366f1',
                color: '#ffffff',
                padding: '2px 7px',
                borderRadius: '10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                letterSpacing: '0.02em',
              }}
            >
              Day 29
            </span>
          </button>
        </div>


        {/* Batch Evaluation (25 Stations) Direct Button */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'batch' ? 'active' : ''}
            onClick={() => handleSelectView('batch')}
          >
            <Layers size={16} /> Batch Evaluation
            <span
              style={{
                marginLeft: '6px',
                background: '#ffd200',
                color: '#002b49',
                padding: '2px 7px',
                borderRadius: '10px',
                fontSize: '0.72rem',
                fontWeight: 800,
                letterSpacing: '0.02em',
              }}
            >
              25 Stations
            </span>
          </button>
        </div>

        {/* Model Registry Button */}
        <div className="dropdown">
          <button
            type="button"
            className={view === 'models' ? 'active' : ''}
            onClick={() => handleSelectView('models')}
          >
            <Cpu size={16} /> Model Registry (E0–E4)
          </button>
        </div>

        {/* External API Docs Link */}
        <div className="nav-external-link">
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
          >
            API Docs <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;
