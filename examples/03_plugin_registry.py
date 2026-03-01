#!/usr/bin/env python3
"""Example: Plugin Registry

Demonstrates registering, discovering, and loading plugins using
the AgentPluginRegistry.

Usage:
    python examples/03_plugin_registry.py

Requirements:
    pip install agentcore-sdk
"""
from __future__ import annotations

from agentcore import (
    AgentPlugin,
    AgentPluginRegistry,
    PluginNotFoundError,
    PluginAlreadyRegisteredError,
)


class SentimentPlugin(AgentPlugin):
    """Plugin that adds basic sentiment analysis capability."""

    name: str = "sentiment-analyzer"
    version: str = "1.0.0"
    description: str = "Analyses sentiment of text input."

    def analyze(self, text: str) -> str:
        positive_words = {"good", "great", "excellent", "happy", "positive"}
        negative_words = {"bad", "terrible", "awful", "unhappy", "negative"}
        words = set(text.lower().split())
        if words & positive_words:
            return "positive"
        if words & negative_words:
            return "negative"
        return "neutral"


class TranslationPlugin(AgentPlugin):
    """Plugin stub for translation capability."""

    name: str = "translator"
    version: str = "2.1.0"
    description: str = "Translates text between languages."

    def translate(self, text: str, target_lang: str = "es") -> str:
        return f"[{target_lang}] {text}"


def main() -> None:
    # Step 1: Create a plugin registry
    registry = AgentPluginRegistry()
    print("AgentPluginRegistry created.")

    # Step 2: Register plugins
    sentiment = SentimentPlugin()
    translation = TranslationPlugin()

    registry.register(sentiment)
    registry.register(translation)
    print(f"Registered {registry.count()} plugin(s).")

    # Step 3: List all plugins
    print("\nRegistered plugins:")
    for plugin_info in registry.list():
        print(f"  [{plugin_info.name}] v{plugin_info.version} — {plugin_info.description}")

    # Step 4: Retrieve and use a plugin
    try:
        loaded_sentiment: SentimentPlugin = registry.get("sentiment-analyzer")  # type: ignore[assignment]
        test_texts = [
            "This is a great product!",
            "The results were terrible.",
            "The meeting is at 3pm.",
        ]
        print("\nSentiment analysis:")
        for text in test_texts:
            result = loaded_sentiment.analyze(text)
            print(f"  '{text}' -> {result}")
    except PluginNotFoundError as error:
        print(f"Plugin not found: {error}")

    # Step 5: Attempt duplicate registration
    try:
        registry.register(SentimentPlugin())
    except PluginAlreadyRegisteredError as error:
        print(f"\nExpected duplicate error: {error}")

    # Step 6: Unregister a plugin
    registry.unregister("translator")
    print(f"\nAfter unregistering 'translator': {registry.count()} plugin(s) remaining.")


if __name__ == "__main__":
    main()
