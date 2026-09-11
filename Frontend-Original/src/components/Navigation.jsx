import { useState, useEffect, useRef } from 'react';
import { Activity, Crosshair, Layers, Cpu, ExternalLink, Menu, X } from 'lucide-react';

export default function Navigation({ view, setView }) {
  const [productsOpen, setProductsOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navRef = useRef(null);

  // Close dropdowns when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (navRef.current && !navRef.current.contains(event.target)) {
        setProductsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, []);

  const handleSelectView = (newView) => {
    setView(newView);
    setProductsOpen(false);
    setMobileMenuOpen(false);
  };

  return (
    <nav className="dropdown-nav" ref={navRef}>
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
          {view === 'sentinel' ? 'Reliability Sentinel' : view === 'batch' ? 'Batch Evaluation' : 'Model Registry'}
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
                marginLeft: '4px',
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
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
          >
            API Docs <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </nav>
  );
}
