"""Pure versioned research specification; never reads settings or credentials."""
from investalo_trading import CryptoEngine, InstrumentRules, PaperSimulator, primitive
from investalo_trading.snapshot import digest


def simulator() -> PaperSimulator:
    # Explicit precision freezes the simulator defaults into the configuration
    # digest. These values are assumptions, not live venue instrument rules.
    engine = CryptoEngine(instrument_rules=(
        InstrumentRules("BTCUSDT"), InstrumentRules("ETHUSDT"),
    ))
    return PaperSimulator(engine=engine)


def specification() -> dict:
    runner = simulator()
    return {
        "strategy_version": runner.engine.config.version,
        "configuration_digest": digest((runner.engine.config, runner.engine.instrument_rules)),
        "cost_digest": digest(runner.costs),
        "configuration": primitive(runner.engine.config),
        "instrument_rules": primitive(runner.engine.instrument_rules),
        "costs": primitive(runner.costs),
        "execution_assumption": "next_open_buy; adverse_low_then_high_then_close; no_terminal_flatten",
    }


def cost_assumptions() -> dict[str, str]:
    runner = simulator()
    return {
        **{name: format(getattr(runner.costs, name), "f") for name in
           ("fee_rate", "spread_fraction", "slippage_fraction")},
        **{name: format(getattr(runner.engine.config, name), "f") for name in
           ("initial_equity", "basket_principal", "basket_cost_reserve")},
    }


def public_source(source: dict) -> dict:
    """Publish reviewed provenance fields; CSV paths and arbitrary URLs stay private."""
    venue, version = source.get("venue"), source.get("api_version")
    url = source.get("url")
    if venue == "bitget" and version == "3":
        if url != "https://api.bitget.com/api/v3/market/history-candles":
            raise ValueError("Unreviewed research source")
    elif (venue, version) in (("synthetic", "fixture-v1"), ("csv", "csv-v1")):
        url = None
    else:
        raise ValueError("Unreviewed research source")
    return {
        "venue": venue, "api_version": version, "url": url,
        "retrieved_at": source["retrieved_at"],
    }
