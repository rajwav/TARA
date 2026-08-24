import re
import json
import logging
import subprocess
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import warnings
from typing import Callable, Any, Optional

# Suppress upstream duckduckgo_search rename warning
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

logger = logging.getLogger("tara.tools")


class ToolRegistry:
    """Lightweight, anti-overengineering tool registry."""

    def __init__(self):
        self.tools: dict[str, Callable] = {}
        self.schemas: list[dict[str, Any]] = []

    def register(self, schema: dict[str, Any]):
        """Decorator to register a tool function with its OpenAI-compatible JSON schema."""
        def decorator(func: Callable):
            name = schema["function"]["name"]
            self.tools[name] = func
            self.schemas.append(schema)
            return func
        return decorator

    def get_schemas(self) -> list[dict[str, Any]]:
        """Return all registered tool schemas."""
        return self.schemas

    def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name with safety checks and parameter filtering."""
        if name not in self.tools:
            return f"Error: Tool '{name}' is not registered."
        try:
            func = self.tools[name]
            import inspect
            sig = inspect.signature(func)
            valid_args = {k: v for k, v in args.items() if k in sig.parameters}
            logger.info(f"Executing tool '{name}' with args: {valid_args}")
            result = func(**valid_args)
            return str(result)
        except Exception as e:
            logger.error(f"Execution error in tool '{name}': {e}")
            return f"Error executing {name}: {e}"


# Global tool registry instance
registry = ToolRegistry()


# ==============================================================================
# 1. SYSTEM TOOLS (Time, Battery, Open Application)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current local time and date on the user's system.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
})
def get_current_time() -> str:
    """Return the current local time formatted cleanly."""
    now = datetime.datetime.now()
    return now.strftime("%I:%M %p on %A, %B %d, %Y")


@registry.register({
    "type": "function",
    "function": {
        "name": "get_battery_status",
        "description": "Check the battery percentage and charging state of the MacBook.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
})
def get_battery_status() -> str:
    """Check battery status via macOS pmset."""
    from tara.actions.system_actions import get_battery_status as _get_battery
    return _get_battery()


@registry.register({
    "type": "function",
    "function": {
        "name": "open_application",
        "description": "Open or launch an application on macOS (e.g., 'Visual Studio Code', 'Calculator', 'Safari', 'Finder', 'Terminal').",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the application to open."
                }
            },
            "required": ["app_name"]
        }
    }
})
def open_application(app_name: str) -> str:
    """Safely open an application on macOS."""
    from tara.actions.app_actions import open_application as _open_app
    return _open_app(app_name)


@registry.register({
    "type": "function",
    "function": {
        "name": "open_project_folder",
        "description": "Open a project directory or folder in macOS Finder.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the project folder on disk (default is current workspace root)."
                }
            },
            "required": []
        }
    }
})
def open_project_folder(path: str = ".") -> str:
    """Open project folder in macOS Finder."""
    from tara.actions.app_actions import open_project_folder as _open_proj
    return _open_proj(path)


@registry.register({
    "type": "function",
    "function": {
        "name": "open_url",
        "description": "Open a web URL in the default macOS web browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open (e.g. 'https://github.com')."
                }
            },
            "required": ["url"]
        }
    }
})
def open_url(url: str) -> str:
    """Open a web URL."""
    from tara.actions.app_actions import open_url as _open_url
    return _open_url(url)


# ==============================================================================
# 2. WEB TOOLS (Web Search & RSS News)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for real-time information and summaries.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default 3).",
                    "default": 3
                }
            },
            "required": ["query"]
        }
    }
})
def search_web(query: str, max_results: int = 3) -> str:
    """Search DuckDuckGo with fallback."""
    # 1. Try duckduckgo_search library if available
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        if results:
            formatted = []
            for idx, r in enumerate(results, 1):
                formatted.append(f"{idx}. {r.get('title')}\n   {r.get('body')}\n   Link: {r.get('href')}")
            return "\n\n".join(formatted)
    except Exception as e:
        logger.debug(f"duckduckgo_search module fallback: {e}")

    # 2. Lightweight fallback using DuckDuckGo Instant Answer API
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "TARA-Assistant/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            abstract = data.get("AbstractText")
            if abstract:
                return f"Summary: {abstract}\nSource: {data.get('AbstractURL')}"

            # Check related topics
            related = data.get("RelatedTopics", [])
            snippets = []
            for item in related[:max_results]:
                if "Text" in item:
                    snippets.append(f"- {item['Text']}")
            if snippets:
                return "\n".join(snippets)

        return f"No instant answers found for '{query}'. Please refine query."
    except Exception as e:
        return f"Web search failed: {e}"


@registry.register({
    "type": "function",
    "function": {
        "name": "fetch_rss_news",
        "description": "Fetch top technology headlines from RSS feeds (e.g. Hacker News, TechCrunch).",
        "parameters": {
            "type": "object",
            "properties": {
                "feed": {
                    "type": "string",
                    "description": "Feed name: 'hackernews' (default) or 'techcrunch'.",
                    "enum": ["hackernews", "techcrunch"],
                    "default": "hackernews"
                }
            },
            "required": []
        }
    }
})
def fetch_rss_news(feed: str = "hackernews") -> str:
    """Fetch and parse top RSS news items using standard library."""
    urls = {
        "hackernews": "https://hnrss.org/frontpage",
        "tech": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "techcrunch": "https://techcrunch.com/feed/"
    }
    feed_url = urls.get(feed.lower(), urls["hackernews"])

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        req = urllib.request.Request(feed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        headlines = []

        for idx, item in enumerate(items[:5], 1):
            title = item.find("title")
            link = item.find("link")
            title_text = title.text.strip() if title is not None and title.text else "No title"
            link_text = link.text.strip() if link is not None and link.text else ""
            headlines.append(f"{idx}. {title_text}")

        if not headlines:
            return f"No news articles currently found for {feed}."

        return f"Top {feed.title()} Headlines:\n" + "\n".join(headlines)
    except Exception as e:
        return f"Failed to fetch RSS news: {e}"


# ==============================================================================
# 3. MEMORY TOOLS (Explicit Memory Request)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "remember_fact",
        "description": "Explicitly store a user fact, preference, project, or goal into long-term memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The category of fact: 'identity', 'project', 'preference', 'goal', or 'general'.",
                    "enum": ["identity", "project", "preference", "goal", "general"]
                },
                "key": {
                    "type": "string",
                    "description": "The key descriptor (e.g. 'name', 'current_project', 'favorite_beverage', 'skill')."
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember."
                }
            },
            "required": ["category", "key", "value"]
        }
    }
})
def remember_fact(category: str, key: str, value: str) -> str:
    """Explicitly remember a fact via MemoryStore."""
    from tara.memory import MemoryStore
    store = MemoryStore()
    res = store.save_fact_safe(category, key, value)
    return f"Stored into memory: category='{category}', key='{key}', value='{value}' (Status: {res.get('action')})"


# ==============================================================================
# 4. VISION TOOLS (On-demand Screen Capture & Analysis)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "capture_screen",
        "description": "Capture the user's current computer screen to a temporary screenshot image.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
})
def capture_screen() -> str:
    """Capture current screen and return temporary image path."""
    from tara.screen_capture import ScreenCapture
    sc = ScreenCapture()
    path = sc.capture_screen()
    if path:
        return f"Screen captured successfully: {path}"
    return "Error: Failed to capture screen. Please check screen recording permissions."


@registry.register({
    "type": "function",
    "function": {
        "name": "analyze_screen",
        "description": "Capture the user's screen and analyze visual elements, terminal errors, UI layouts, or code windows.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Specific question or focus area (e.g. 'What is causing this terminal error?' or 'Review this UI design')."
                }
            },
            "required": []
        }
    }
})
def analyze_screen(question: str = "Analyze what is visible on screen, identify errors, and suggest fixes.") -> str:
    """Capture screen on-demand, run vision analysis, and clean up temporary screenshot."""
    from tara.screen_capture import ScreenCapture
    from tara.vision import VisionEngine

    sc = ScreenCapture()
    img_path = sc.capture_screen()

    if not img_path:
        return "Unable to capture screen. Please ensure screen capture permission is enabled."

    try:
        engine = VisionEngine()
        analysis = engine.analyze_image(img_path, question=question)

        desc = analysis.get("description", "No description available.")
        issues = analysis.get("issues", [])
        suggestions = analysis.get("suggestions", [])

        output = [f"**Screen Analysis:**\n{desc}"]
        if issues:
            output.append("\n**Identified Issues:**\n" + "\n".join(f"- {iss}" for iss in issues))
        if suggestions:
            output.append("\n**Suggestions:**\n" + "\n".join(f"- {sug}" for sug in suggestions))

        return "\n".join(output)
    finally:
        sc.cleanup(img_path)


# ==============================================================================
# 5. DOCUMENT TOOLS (PDF, Markdown, Text, and Code Understanding)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "read_document",
        "description": "Read and extract text content from a file (PDF, TXT, Markdown, JSON, YAML, or source code).",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the document or source file on disk."
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of characters to extract (default 4000)."
                }
            },
            "required": ["path"]
        }
    }
})
def read_document(path: str, max_chars: int = 4000) -> str:
    """Extract and read text from a document."""
    from tara.documents import DocumentEngine
    engine = DocumentEngine()
    try:
        content = engine.extract_text(path, max_chars=max_chars)
        return f"**Content of '{path}':**\n\n{content}"
    except Exception as e:
        return f"Failed to read document '{path}': {e}"


@registry.register({
    "type": "function",
    "function": {
        "name": "summarize_document",
        "description": "Summarize a document, paper, notes file, or source code file into a structured overview.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the document file (PDF, TXT, MD, etc.)."
                }
            },
            "required": ["path"]
        }
    }
})
def summarize_document(path: str) -> str:
    """Summarize a document using DocumentEngine."""
    from tara.documents import DocumentEngine
    engine = DocumentEngine()
    return engine.summarize_document(path)


@registry.register({
    "type": "function",
    "function": {
        "name": "analyze_document",
        "description": "Ask a question or request in-depth analysis of a document or source file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the document file on disk."
                },
                "question": {
                    "type": "string",
                    "description": "Specific question to answer from the document."
                }
            },
            "required": ["path", "question"]
        }
    }
})
def analyze_document(path: str, question: str) -> str:
    """Answer a specific question grounded in a document."""
    from tara.documents import DocumentEngine
    engine = DocumentEngine()
    return engine.answer_from_document(path, question)


# ==============================================================================
# 6. KNOWLEDGE WORKSPACE TOOLS (Searchable Personal Notes & Documents)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "search_workspace",
        "description": "Search personal documents, project files, notes, and code in the knowledge workspace using fast keyword/full-text search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords or search terms (e.g. 'transformers', 'FastAPI', 'rate limiter', 'auth bug')."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5)."
                }
            },
            "required": ["query"]
        }
    }
})
def search_workspace(query: str, limit: int = 5) -> str:
    """Search personal knowledge workspace using SQLite FTS5 index."""
    from tara.workspace import KnowledgeWorkspace
    ws = KnowledgeWorkspace()
    results = ws.search_knowledge(query, limit=limit)

    if not results:
        return f"No documents in the knowledge workspace matched '{query}'."

    output = [f"**Found {len(results)} matching document(s) for '{query}':**\n"]
    for i, r in enumerate(results, 1):
        output.append(f"{i}. **{r['filename']}** (`{r['file_type']}`)\n   - **Location:** `{r['path']}`\n   - **Keywords:** {r['keywords']}\n   - **Preview:** {r['summary']}")

    return "\n".join(output)


@registry.register({
    "type": "function",
    "function": {
        "name": "index_workspace",
        "description": "Index a file or directory into the personal knowledge workspace for fast searching.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file or folder to index (e.g. '.' or 'notes/')."
                }
            },
            "required": ["path"]
        }
    }
})
def index_workspace(path: str = ".") -> str:
    """Index files into personal knowledge workspace."""
    import os
    from tara.workspace import KnowledgeWorkspace
    ws = KnowledgeWorkspace()

    if not os.path.exists(path):
        return f"Path does not exist: {path}"

    if os.path.isdir(path):
        count = ws.index_directory(path)
        summary = ws.get_workspace_summary()
        return f"Successfully indexed {count} file(s) from '{path}'. Total workspace documents: {summary['total_documents']}."
    else:
        res = ws.index_file(path)
        return f"Successfully indexed '{res['filename']}' ({res['file_type']}) with keywords: {res['keywords']}."


# ==============================================================================
# 7. SAFE FILE ACTIONS (Create, Move, Info, List)
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": "List files, subfolders, sizes, and timestamps within a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default is current folder '.')."
                }
            },
            "required": []
        }
    }
})
def list_directory(path: str = ".") -> str:
    """List directory contents."""
    from tara.actions.file_actions import list_directory as _list_dir
    return _list_dir(path)


@registry.register({
    "type": "function",
    "function": {
        "name": "create_file",
        "description": "Safely create a new file with specified text content on disk.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Target file path."
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file."
                }
            },
            "required": ["path", "content"]
        }
    }
})
def create_file(path: str, content: str = "") -> str:
    """Create a file safely."""
    from tara.actions.file_actions import create_file as _create_file
    return _create_file(path, content)


@registry.register({
    "type": "function",
    "function": {
        "name": "create_folder",
        "description": "Create a new folder or directory path safely.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to create."
                }
            },
            "required": ["path"]
        }
    }
})
def create_folder(path: str) -> str:
    """Create a directory."""
    from tara.actions.file_actions import create_folder as _create_folder
    return _create_folder(path)


@registry.register({
    "type": "function",
    "function": {
        "name": "move_file",
        "description": "Move or rename a file or directory from source to destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source path to move or rename."
                },
                "destination": {
                    "type": "string",
                    "description": "Destination file or folder path."
                }
            },
            "required": ["source", "destination"]
        }
    }
})
def move_file(source: str, destination: str) -> str:
    """Move or rename a file."""
    from tara.actions.file_actions import move_file as _move_file
    return _move_file(source, destination)


@registry.register({
    "type": "function",
    "function": {
        "name": "get_file_info",
        "description": "Get detailed metadata, size, timestamps, and permissions for a file or directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file or directory."
                }
            },
            "required": ["path"]
        }
    }
})
def get_file_info(path: str) -> str:
    """Retrieve file metadata."""
    from tara.actions.file_actions import get_file_info as _get_info
    return _get_info(path)


# ==============================================================================
# 8. SYSTEM MONITORING & METRICS ACTIONS
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "get_cpu_usage",
        "description": "Check current macOS CPU load, core count, and user/system breakdown.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
})
def get_cpu_usage() -> str:
    """Check CPU usage."""
    from tara.actions.system_actions import get_cpu_usage as _get_cpu
    return _get_cpu()


@registry.register({
    "type": "function",
    "function": {
        "name": "get_memory_usage",
        "description": "Check macOS unified memory (RAM) usage (Total, Used, Available in GB).",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
})
def get_memory_usage() -> str:
    """Check Memory usage."""
    from tara.actions.system_actions import get_memory_usage as _get_mem
    return _get_mem()


@registry.register({
    "type": "function",
    "function": {
        "name": "get_storage_usage",
        "description": "Check primary disk storage capacity, used space, and free available gigabytes.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
})
def get_storage_usage() -> str:
    """Check Storage usage."""
    from tara.actions.system_actions import get_storage_usage as _get_storage
    return _get_storage()


@registry.register({
    "type": "function",
    "function": {
        "name": "get_running_apps",
        "description": "List currently active and open applications on macOS.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
})
def get_running_apps() -> str:
    """Check running GUI apps."""
    from tara.actions.system_actions import get_running_apps as _get_apps
    return _get_apps()


# ==============================================================================
# 9. BROWSER ACTIONS
# ==============================================================================

@registry.register({
    "type": "function",
    "function": {
        "name": "open_browser_url",
        "description": "Open a website URL in the default macOS web browser.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to open (e.g. 'https://github.com')."
                }
            },
            "required": ["url"]
        }
    }
})
def open_browser_url(url: str) -> str:
    """Open URL in default browser."""
    from tara.actions.browser_actions import open_browser_url as _open_burl
    return _open_burl(url)




