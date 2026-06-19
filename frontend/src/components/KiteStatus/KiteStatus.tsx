/**
 * KiteStatus — Phase 2
 * Shows Kite WebSocket connection status, token validity, and reconnect controls.
 * Displayed prominently in the Dashboard header.
 */

import { useState, useEffect, useCallback } from "react";
import { kiteApi } from "../../services/api";

interface KiteStatusData {
  authenticated: boolean;
  ticker_connected: boolean;
  ticker_running: boolean;
  instruments_loaded: boolean;
  subscribed_options: number;
  api_key_masked: string | null;
}

export default function KiteStatus() {
  const [status, setStatus] = useState<KiteStatusData | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await kiteApi.getStatus();
      setStatus(data);
    } catch {
      // silently ignore — shows as disconnected
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10_000); // refresh every 10s
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleLogin = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await kiteApi.getLoginUrl();
      if (!data.login_url) throw new Error("No login URL returned");
      // Open Kite login in new tab
      window.open(data.login_url, "_blank", "noopener,noreferrer");
      setMessage("Kite login page opened. Complete login and return here.");
    } catch (err: any) {
      setMessage(`Error: ${err.response?.data?.detail || err.message || "Failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleStartFeed = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const data = await kiteApi.startFeed();
      setMessage(data.message);
      await fetchStatus();
    } catch (err: any) {
      setMessage(`Error: ${err.response?.data?.detail || err.message || "Failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    setLoading(true);
    try {
      const data = await kiteApi.validateToken();
      setMessage(data.message);
      await fetchStatus();
    } catch {
      setMessage("Validation check failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadInstruments = async () => {
    setLoading(true);
    try {
      const data = await kiteApi.loadInstruments();
      setMessage(data.message);
      await fetchStatus();
    } catch {
      setMessage("Failed to load instruments");
    } finally {
      setLoading(false);
    }
  };


  const Dot = ({ ok }: { ok: boolean }) => (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full mr-1.5 ${
        ok ? "bg-green-400" : "bg-red-400"
      }`}
    />
  );

  return (
    <div className="bg-navy-900 border border-navy-700 rounded-xl p-4 space-y-3 shadow-lg">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-navy-100 uppercase tracking-wide">
          Zerodha Kite
        </h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            status?.ticker_connected
              ? "bg-green-900 text-green-300"
              : status?.authenticated
              ? "bg-yellow-900 text-yellow-300"
              : "bg-navy-800 text-navy-300 border border-navy-700"
          }`}
        >
          {status?.ticker_connected
            ? "LIVE"
            : status?.authenticated
            ? "Authenticated"
            : "Not Connected"}
        </span>
      </div>

      {status && (
        <div className="grid grid-cols-2 gap-1.5 text-xs text-navy-300">
          <div>
            <Dot ok={status.authenticated} />
            Auth token
          </div>
          <div>
            <Dot ok={status.ticker_connected} />
            WebSocket feed
          </div>
          <div>
            <Dot ok={status.instruments_loaded} />
            NFO instruments
          </div>
          <div>
            <Dot ok={status.subscribed_options > 0} />
            Options streaming ({status.subscribed_options})
          </div>
          {status.api_key_masked && (
            <div className="col-span-2 text-navy-400 font-mono text-[11px]">
              API key: {status.api_key_masked}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {!status?.authenticated ? (
          <button
            onClick={handleLogin}
            disabled={loading}
            className="text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg font-medium disabled:opacity-50 transition duration-150 shadow-md shadow-blue-950/20"
          >
            {loading ? "Opening..." : "Login to Kite"}
          </button>
        ) : (
          <>
            {!status.ticker_running && (
              <button
                onClick={handleStartFeed}
                disabled={loading}
                className="text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg font-medium disabled:opacity-50 transition duration-150 shadow-md shadow-green-950/20"
              >
                {loading ? "Starting..." : "▶ Start Live Feed"}
              </button>
            )}
            {!status.instruments_loaded && (
              <button
                onClick={handleLoadInstruments}
                disabled={loading}
                className="text-xs bg-purple-600 hover:bg-purple-700 text-white px-3 py-1.5 rounded-lg font-medium disabled:opacity-50 transition duration-150 shadow-md shadow-purple-950/20"
              >
                Load Instruments
              </button>
            )}
            <button
              onClick={handleValidate}
              disabled={loading}
              className="text-xs bg-navy-800 hover:bg-navy-700 text-navy-200 border border-navy-700 px-3 py-1.5 rounded-lg font-medium disabled:opacity-50 transition duration-150"
            >
              Validate Token
            </button>
          </>
        )}
      </div>

      {message && (
        <p
          className={`text-xs px-2 py-1.5 rounded ${
            message.startsWith("Error")
              ? "bg-red-900/40 text-red-300"
              : "bg-blue-900/40 text-blue-300"
          }`}
        >
          {message}
        </p>
      )}

      {/* Token expiry reminder banner */}
      {status?.authenticated && !status.ticker_connected && (
        <p className="text-xs text-yellow-400 bg-yellow-900/20 px-2 py-1 rounded">
          ⚠ Kite tokens expire daily at ~6 AM. Re-login if token is expired.
        </p>
      )}
    </div>

  );
}
