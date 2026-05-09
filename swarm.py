import os
from dotenv import load_dotenv

# ── Kill tracing BEFORE anything imports `agents.tracing` ───────────────────
# The OpenAI Agents SDK creates a background exporter thread that phones
# api.openai.com regardless of set_tracing_disabled(). We monkey-patch
# get_trace_provider() to return a no-op so no HTTP calls ever happen.
import agents.tracing.setup as _tracing_setup
import agents.tracing.provider as _tracing_provider
from agents.tracing.spans import NoOpSpan
from agents.tracing.traces import NoOpTrace

class _NoOpTraceProvider(_tracing_provider.TraceProvider):
    """Provider that never creates traces/spans or starts exporter threads."""
    def register_processor(self, processor): pass
    def set_processors(self, processors): pass
    def get_current_trace(self): return None
    def get_current_span(self): return None
    def set_disabled(self, disabled: bool): pass
    def time_iso(self):
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    def gen_trace_id(self):
        import uuid
        return f"trace_{uuid.uuid4().hex}"
    def gen_span_id(self):
        import uuid
        return f"span_{uuid.uuid4().hex[:24]}"
    def gen_group_id(self):
        import uuid
        return f"group_{uuid.uuid4().hex[:24]}"
    def create_trace(self, name, trace_id=None, group_id=None, metadata=None, disabled=False, tracing=None):
        return NoOpTrace()
    def create_span(self, span_data, span_id=None, parent=None, disabled=False):
        return NoOpSpan(span_data)
    def shutdown(self): pass

_noop = _NoOpTraceProvider()
_tracing_setup.get_trace_provider = lambda: _noop
# Override the module-level caches too
_tracing_setup.GLOBAL_TRACE_PROVIDER = _noop

# Also nuke the set_tracing* functions so nothing tries to reconfigure
import agents.tracing as _tracing
_tracing.set_tracing_disabled = lambda disabled: None
_tracing.set_tracing_export_api_key = lambda api_key: None

from patches.patch_agency_swarm_dual_comms import apply_dual_comms_patch
from patches.patch_file_attachment_refs import apply_file_attachment_reference_patch
from patches.patch_ipython_interpreter_composio import apply_ipython_composio_context_patch
from patches.patch_utf8_file_reads import apply_utf8_file_read_patch

load_dotenv()

apply_utf8_file_read_patch()
apply_dual_comms_patch()
apply_file_attachment_reference_patch()
apply_ipython_composio_context_patch()


def create_agency(load_threads_callback=None):
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from orchestrator import create_orchestrator
    from virtual_assistant import create_virtual_assistant
    from deep_research import create_deep_research
    from data_analyst_agent import create_data_analyst
    from slides_agent import create_slides_agent
    from docs_agent import create_docs_agent
    from video_generation_agent import create_video_generation_agent
    from image_generation_agent import create_image_generation_agent

    orchestrator = create_orchestrator()
    virtual_assistant = create_virtual_assistant()
    deep_research = create_deep_research()
    data_analyst = create_data_analyst()
    slides_agent = create_slides_agent()
    docs_agent = create_docs_agent()
    video_generation_agent = create_video_generation_agent()
    image_generation_agent = create_image_generation_agent()

    all_agents = [
        orchestrator,
        virtual_assistant,
        slides_agent,
        deep_research,
        data_analyst,
        docs_agent,
        video_generation_agent,
        image_generation_agent,
    ]

    send_message_flows = [
        (orchestrator, specialist, SendMessage)
        for specialist in all_agents
        if specialist is not orchestrator
    ]

    handoff_flows = [
        (a > b, Handoff)
        for a in all_agents
        for b in all_agents
        if a is not b
    ]

    agency = Agency(
        *all_agents,
        communication_flows=send_message_flows + handoff_flows,
        name="OpenSwarm",
        shared_instructions="shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )

    return agency

if __name__ == "__main__":
    agency = create_agency()
    agency.tui(show_reasoning=True, reload=False)
