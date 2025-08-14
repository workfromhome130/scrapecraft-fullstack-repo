"""
Unified Conversational Agent for ScrapeCraft
A Cursor-like intelligent assistant for web scraping that learns and improves.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import asyncio
import hashlib
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field
import redis.asyncio as redis

from app.config import settings
from app.services.openrouter import get_llm
from app.services.scrapegraph import ScrapingService


class ConversationContext(BaseModel):
    """Context for a conversation thread."""
    pipeline_id: str
    user_id: Optional[str] = None
    urls: List[str] = Field(default_factory=list)
    schema: Dict[str, Any] = Field(default_factory=dict)
    generated_code: str = ""
    current_phase: str = "initial"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Intent(BaseModel):
    """Analyzed user intent."""
    primary_intent: str  # add_urls, define_schema, generate_code, run_pipeline, ask_question, reuse_pipeline
    confidence: float = 0.0
    entities: Dict[str, Any] = Field(default_factory=dict)
    suggested_actions: List[str] = Field(default_factory=list)
    similar_pipelines: List[str] = Field(default_factory=list)


class UnifiedScrapingAgent:
    """
    Unified conversational agent that acts like Cursor for web scraping.
    Maintains context, learns from patterns, and creates reusable pipelines.
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        self.redis_client: Optional[redis.Redis] = None
        self.conversation_ttl = 86400 * 7  # 7 days
        
        # Initialize services (will be imported separately)
        self.pipeline_repo = None  # Will be initialized with PipelineRepository
        self.pattern_learner = None  # Will be initialized with PatternLearner
        
        self.system_prompt = self._build_system_prompt()
    
    async def initialize(self):
        """Initialize async components."""
        # Connect to Redis for conversation memory
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Initialize repository and learning services
        from app.services.pipeline_repository import PipelineRepository
        from app.services.pattern_learner import PatternLearner
        
        self.pipeline_repo = PipelineRepository()
        await self.pipeline_repo.initialize()
        
        self.pattern_learner = PatternLearner()
        await self.pattern_learner.initialize()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        return """You are ScrapeCraft AI, an intelligent conversational assistant for web scraping, similar to how Cursor works for coding.

Your capabilities:
1. **Conversational Understanding**: Maintain context across conversations and learn from interactions
2. **Pipeline Creation**: Help users build reusable scraping pipelines with ScrapeGraphAI
3. **Pattern Recognition**: Identify and suggest optimizations based on successful patterns
4. **Code Generation**: Generate production-ready Python code using async ScrapeGraphAI client
5. **Pipeline Reuse**: Find and adapt existing pipelines for new use cases

Key behaviors:
- Be conversational and helpful, like a pair programmer
- Proactively suggest improvements and optimizations
- Learn from each interaction to improve future suggestions
- Remember context across sessions
- Offer to save successful pipelines for reuse

When generating code, ALWAYS use the async ScrapeGraphAI pattern with prompt-based extraction:
```python
import asyncio
from scrapegraph_py import AsyncClient

async def scrape_data(urls: List[str], api_key: str):
    prompt = \"\"\"Extract the following information:
    - field1: description
    - field2: description
    
    Return as JSON with these field names.\"\"\"
    
    async with AsyncClient(api_key=api_key) as client:
        result = await client.smartscraper(
            website_url=url,
            user_prompt=prompt
        )
        # Process result
```

Focus on creating an excellent developer experience through intelligent assistance and continuous learning."""
    
    async def process_message(
        self,
        message: str,
        pipeline_id: str,
        user_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process a user message with full conversational understanding.
        
        Args:
            message: User's message
            pipeline_id: Unique pipeline identifier
            user_id: Optional user identifier
            context: Optional existing context
        
        Returns:
            Response with suggestions, code, and actions
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # 1. Load or create conversation context
            conv_context = await self._get_or_create_context(pipeline_id, user_id, context)
            
            # 2. Add message to conversation history
            await self._add_to_conversation(pipeline_id, "user", message)
            
            # 3. Analyze intent with full context
            intent = await self._analyze_intent_with_context(message, conv_context)
            
            # Validate intent is correct type
            if not isinstance(intent, Intent):
                raise TypeError(f"Intent analysis returned {type(intent)} instead of Intent")
            
            # 4. Find similar pipelines if relevant
            similar_pipelines = []
            if intent.confidence > 0.7 and intent.similar_pipelines:
                similar_pipelines = await self._find_similar_pipelines(intent, conv_context)
            
            # 5. Process based on intent
            response = await self._process_by_intent(intent, message, conv_context, similar_pipelines)
            
            # Ensure response is a dictionary
            if not isinstance(response, dict):
                raise TypeError(f"Handler returned {type(response)} instead of dict")
            
            # 6. Learn from this interaction
            if self.pattern_learner:
                await self.pattern_learner.learn_from_interaction(
                    intent=intent,
                    context=conv_context,
                    response=response
                )
            
            # 7. Update context
            if "updated_context" in response:
                await self._update_context(pipeline_id, response["updated_context"])
            else:
                await self._update_context(pipeline_id, conv_context.model_dump())
            
            # 8. Add response to conversation
            await self._add_to_conversation(pipeline_id, "assistant", response["message"])
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Error in process_message: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Ensure conv_context is defined for error response
            context_data = {}
            try:
                if 'conv_context' in locals() and conv_context:
                    context_data = conv_context.model_dump()
            except:
                pass
            
            return {
                "message": f"I encountered an error: {str(e)}. Let me help you resolve this.",
                "status": "error",
                "error": str(e),
                "suggestions": ["Check your API keys", "Verify the URLs are accessible", "Try a simpler query"],
                "context": context_data,
                "updated_context": context_data
            }
    
    async def _get_or_create_context(
        self,
        pipeline_id: str,
        user_id: Optional[str],
        initial_context: Optional[Dict]
    ) -> ConversationContext:
        """Get existing context or create new one."""
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating context for pipeline {pipeline_id}, initial_context type: {type(initial_context)}")
        if initial_context:
            logger.info(f"Initial context keys: {initial_context.keys() if isinstance(initial_context, dict) else 'Not a dict'}")
        
        # Try to load from Redis
        context_key = f"context:{pipeline_id}"
        stored_context = await self.redis_client.get(context_key)
        
        if stored_context:
            context_data = json.loads(stored_context)
            # Merge with any updates from initial_context
            if initial_context and isinstance(initial_context, dict):
                # Only update if the incoming values are non-empty
                if initial_context.get('urls'):
                    context_data['urls'] = initial_context['urls']
                if initial_context.get('schema'):
                    context_data['schema'] = initial_context['schema']
                if initial_context.get('code') or initial_context.get('generated_code'):
                    context_data['generated_code'] = initial_context.get('code') or initial_context.get('generated_code')
            return ConversationContext(**context_data)
        
        # Create new context - filter out non-ConversationContext fields
        filtered_context = {}
        if initial_context and isinstance(initial_context, dict):
            # Only keep fields that are part of ConversationContext
            valid_fields = {"urls", "schema", "generated_code", "current_phase", "metadata"}
            
            # Map any misnamed fields and skip invalid ones
            for k, v in initial_context.items():
                if k in valid_fields:
                    filtered_context[k] = v
                elif k == "phase":  # Map 'phase' to 'current_phase'
                    filtered_context["current_phase"] = v
                elif k == "status":  # Map 'status' to 'current_phase'
                    filtered_context["current_phase"] = v
                elif k == "code":  # Map 'code' to 'generated_code'
                    filtered_context["generated_code"] = v
                # Skip collaborators and other non-ConversationContext fields
        
        try:
            context = ConversationContext(
                pipeline_id=pipeline_id,
                user_id=user_id,
                **filtered_context
            )
        except Exception as e:
            logger.error(f"Error creating context: {e}")
            logger.error(f"Filtered context: {filtered_context}")
            # Create minimal context on error
            context = ConversationContext(
                pipeline_id=pipeline_id,
                user_id=user_id
            )
        
        # Store in Redis
        await self.redis_client.set(
            context_key,
            json.dumps(context.model_dump(mode='json')),
            ex=self.conversation_ttl
        )
        
        return context
    
    async def _add_to_conversation(self, pipeline_id: str, role: str, content: str):
        """Add a message to conversation history."""
        history_key = f"conversation:{pipeline_id}"
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add to Redis list
        await self.redis_client.lpush(history_key, json.dumps(message))
        
        # Trim to keep only last 50 messages
        await self.redis_client.ltrim(history_key, 0, 49)
        
        # Set expiration
        await self.redis_client.expire(history_key, self.conversation_ttl)
    
    async def _get_conversation_history(
        self,
        pipeline_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent conversation history."""
        history_key = f"conversation:{pipeline_id}"
        
        # Get recent messages
        messages = await self.redis_client.lrange(history_key, 0, limit - 1)
        
        return [json.loads(msg) for msg in messages]
    
    async def _analyze_intent_with_context(
        self,
        message: str,
        context: ConversationContext
    ) -> Intent:
        """Analyze user intent with full conversation context."""
        # Get conversation history
        history = await self._get_conversation_history(context.pipeline_id, limit=5)
        
        # Build context for intent analysis
        history_text = "\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in reversed(history)
        ])
        
        prompt = f"""Analyze this message in the context of a web scraping conversation.

Conversation history:
{history_text}

Current message: "{message}"

Current pipeline state:
- URLs: {len(context.urls)} configured
- Schema: {'defined' if context.schema else 'not defined'}
- Code: {'generated' if context.generated_code else 'not generated'}
- Phase: {context.current_phase}

Determine:
1. Primary intent (one of: add_urls, define_schema, generate_code, run_pipeline, ask_question, reuse_pipeline, optimize_pipeline)
2. Confidence level (0.0 to 1.0)
3. Key entities (URLs, field names, data types, etc.)
4. Suggested next actions
5. Whether to search for similar pipelines

Respond in JSON:
{{
    "primary_intent": "string",
    "confidence": float,
    "entities": {{}},
    "suggested_actions": [],
    "should_search_similar": boolean
}}"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an intent analyzer. Respond only in valid JSON."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.llm.ainvoke(messages)
            intent_data = json.loads(response.content.strip())
            
            return Intent(
                primary_intent=intent_data["primary_intent"],
                confidence=intent_data["confidence"],
                entities=intent_data.get("entities", {}),
                suggested_actions=intent_data.get("suggested_actions", []),
                similar_pipelines=[]  # Will be populated if needed
            )
            
        except Exception as e:
            # Fallback intent detection
            return Intent(
                primary_intent="ask_question",
                confidence=0.5,
                entities={},
                suggested_actions=["clarify_request"],
                similar_pipelines=[]
            )
    
    async def _find_similar_pipelines(
        self,
        intent: Intent,
        context: ConversationContext
    ) -> List[Dict]:
        """Find similar pipelines from repository."""
        if not self.pipeline_repo:
            return []
        
        # Build search query from intent and context
        search_query = {
            "description": intent.entities.get("description", ""),
            "urls": context.urls[:3] if context.urls else [],
            "schema_fields": list(context.schema.keys()) if context.schema else [],
            "intent": intent.primary_intent
        }
        
        # Search for similar pipelines
        similar = await self.pipeline_repo.find_similar(search_query, limit=3)
        
        return similar
    
    async def _process_by_intent(
        self,
        intent: Intent,
        message: str,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Process message based on detected intent."""
        
        # Map intents to processing methods
        intent_handlers = {
            "add_urls": self._handle_add_urls,
            "define_schema": self._handle_define_schema,
            "generate_code": self._handle_generate_code,
            "run_pipeline": self._handle_run_pipeline,
            "reuse_pipeline": self._handle_reuse_pipeline,
            "optimize_pipeline": self._handle_optimize_pipeline,
            "ask_question": self._handle_general_question
        }
        
        handler = intent_handlers.get(intent.primary_intent, self._handle_general_question)
        
        return await handler(message, intent, context, similar_pipelines)
    
    async def _handle_add_urls(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle URL addition requests."""
        urls_to_add = intent.entities.get("urls", [])
        search_query = intent.entities.get("search_query")
        
        if search_query and not urls_to_add:
            # Search for URLs
            search_results = await self.scraping_service.search_urls(search_query, max_results=10)
            urls_to_add = [r.get("url") for r in search_results if r.get("url")]
        
        # Add URLs to context
        new_urls = [url for url in urls_to_add if url not in context.urls]
        context.urls.extend(new_urls)
        
        # Generate response
        if len(new_urls) > 0:
            response_message = f"I've added {len(new_urls)} URLs to your pipeline.\n\n"
        else:
            response_message = f"URLs are already in your pipeline (total: {len(context.urls)}).\n\n"
        
        if similar_pipelines:
            response_message += "I found similar pipelines that might help:\n"
            for pipe in similar_pipelines[:2]:
                response_message += f"- {pipe['name']}: {pipe['description']}\n"
            response_message += "\nWould you like to use one as a template?\n\n"
        
        # Check if we already have a schema
        if context.schema:
            response_message += f"You already have a schema defined with {len(context.schema)} fields. Ready to generate the scraping code?"
        else:
            response_message += "Next, let's define what data you want to extract. What fields do you need?"
        
        return {
            "message": response_message,
            "status": "success",
            "urls": context.urls,
            "similar_pipelines": similar_pipelines,
            "suggested_actions": ["define_schema", "use_template"],
            "updated_context": context.model_dump()
        }
    
    async def _handle_define_schema(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle schema definition requests."""
        # Extract field definitions from message
        fields = intent.entities.get("fields", {})
        
        if not fields:
            # Always suggest fields based on the user's message
            fields = await self._suggest_schema_fields(context.urls[:3] if context.urls else [], message)
        
        # Ensure fields is a dictionary
        if isinstance(fields, list):
            # Convert list to dictionary if needed
            fields_dict = {}
            for item in fields:
                if isinstance(item, dict):
                    # If it's a dict with 'name' and 'type', extract them
                    if 'name' in item:
                        fields_dict[item['name']] = item.get('type', 'str')
                    else:
                        # Otherwise use the first key-value pair
                        for k, v in item.items():
                            fields_dict[k] = v
                            break
                elif isinstance(item, str):
                    # If it's just a string, use it as both name and type hint
                    fields_dict[item] = 'str'
            fields = fields_dict
        elif not isinstance(fields, dict):
            # Fallback to default fields if we get unexpected type
            fields = {
                "title": "str",
                "content": "str",
                "url": "str"
            }
        
        # Update context schema
        context.schema.update(fields)
        
        # Generate the extraction prompt that will be used
        response_message = "I'll extract the following information using this prompt:\n\n"
        response_message += "```\n"
        response_message += "Extract the following information from the webpage:\n"
        
        # Generate field descriptions for the prompt
        for field_name, field_type in fields.items():
            # Create a human-readable description
            field_description = field_name.replace('_', ' ').lower()
            response_message += f"- {field_name}: {field_description}\n"
        
        response_message += "\nReturn the data as JSON with these exact field names.\n"
        response_message += "```\n\n"
        response_message += "This prompt will be used to extract the data. Ready to generate the scraping code?"
        
        return {
            "message": response_message,
            "status": "success",
            "schema": context.schema,
            "suggested_actions": ["generate_code", "modify_fields"],
            "updated_context": context.model_dump()
        }
    
    async def _handle_generate_code(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle code generation requests."""
        if not context.urls or not context.schema:
            return {
                "message": "I need both URLs and a schema to generate code. What would you like to scrape?",
                "status": "needs_info",
                "suggested_actions": ["add_urls", "define_schema"]
            }
        
        # Generate optimized code
        code = await self._generate_optimized_code(context)
        context.generated_code = code
        
        # Check for optimization opportunities
        optimizations = []
        if self.pattern_learner:
            optimizations = await self.pattern_learner.suggest_optimizations(context)
        
        response_message = "I've generated optimized scraping code for you!\n\n"
        response_message += "The code includes:\n"
        response_message += "- Async execution for better performance\n"
        response_message += "- Error handling and retries\n"
        response_message += "- Structured data extraction with Pydantic\n"
        
        if optimizations:
            response_message += "\nSuggested optimizations:\n"
            for opt in optimizations[:3]:
                response_message += f"- {opt['suggestion']}\n"
        
        response_message += "\nReady to run the pipeline?"
        
        return {
            "message": response_message,
            "status": "success",
            "code": code,
            "optimizations": optimizations,
            "suggested_actions": ["run_pipeline", "save_pipeline", "optimize_code"],
            "updated_context": context.model_dump()
        }
    
    async def _handle_run_pipeline(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle pipeline execution requests."""
        if not context.urls or not context.schema:
            return {
                "message": "The pipeline isn't ready yet. Let me help you set it up first.",
                "status": "needs_setup",
                "suggested_actions": ["add_urls", "define_schema"]
            }
        
        # Check if we have generated code
        if not context.generated_code:
            # Generate the code first
            context.generated_code = await self._generate_optimized_code(context)
        
        # Execute the pipeline using ScrapeGraphAI
        try:
            results = await self.scraping_service.execute_pipeline(
                urls=context.urls,
                schema=context.schema,
                prompt=f"Extract {', '.join(context.schema.keys())}"
            )
        except Exception as e:
            # If direct execution fails, inform user about the code
            response_message = "I've generated the code but couldn't execute it directly. "
            response_message += f"Error: {str(e)}\n\n"
            response_message += "Here's your code that you can run locally:\n\n"
            response_message += f"```python\n{context.generated_code}\n```\n\n"
            response_message += "Make sure you have your SCRAPEGRAPH_API_KEY configured."
            
            return {
                "message": response_message,
                "status": "execution_failed",
                "code": context.generated_code,
                "error": str(e),
                "suggested_actions": ["save_pipeline", "copy_code"],
                "updated_context": context.model_dump()
            }
        
        # Analyze results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        response_message = f"Pipeline execution complete!\n\n"
        response_message += f"✅ Successfully scraped: {len(successful)}/{len(results)} URLs\n"
        
        if failed:
            response_message += f"⚠️ Failed URLs: {len(failed)}\n"
        
        # Learn from execution
        if self.pattern_learner:
            await self.pattern_learner.learn_from_execution(context, results)
        
        response_message += "\nWould you like to save this pipeline for future use?"
        
        return {
            "message": response_message,
            "status": "success",
            "results": results,
            "suggested_actions": ["save_pipeline", "refine_results", "export_data"],
            "updated_context": context.model_dump()
        }
    
    async def _handle_reuse_pipeline(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle pipeline reuse requests."""
        if not similar_pipelines:
            return {
                "message": "I couldn't find similar pipelines. Let's create a new one! What would you like to scrape?",
                "status": "no_matches",
                "suggested_actions": ["create_new_pipeline"]
            }
        
        # Select best matching pipeline
        selected = similar_pipelines[0]
        
        # Adapt pipeline to current context
        adapted_context = await self._adapt_pipeline(selected, context)
        
        response_message = f"I found a pipeline that matches your needs: '{selected['name']}'\n\n"
        response_message += f"Description: {selected['description']}\n"
        response_message += f"Success rate: {selected.get('success_rate', 0):.1%}\n\n"
        response_message += "I've adapted it for your use case. Would you like to review the configuration?"
        
        return {
            "message": response_message,
            "status": "success",
            "adapted_pipeline": selected,
            "suggested_actions": ["review_pipeline", "run_pipeline", "modify_pipeline"],
            "updated_context": adapted_context.model_dump()
        }
    
    async def _handle_optimize_pipeline(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle pipeline optimization requests."""
        optimizations = []
        
        if self.pattern_learner:
            optimizations = await self.pattern_learner.suggest_optimizations(context)
        
        if not optimizations:
            return {
                "message": "Your pipeline looks well-optimized! The current configuration should work efficiently.",
                "status": "already_optimized",
                "suggested_actions": ["run_pipeline", "save_pipeline"]
            }
        
        # Apply optimizations
        optimized_context = await self._apply_optimizations(context, optimizations)
        
        response_message = "I've optimized your pipeline with the following improvements:\n\n"
        for opt in optimizations[:3]:
            response_message += f"✨ {opt['suggestion']}\n"
            response_message += f"   Expected improvement: {opt.get('improvement', 'Better performance')}\n\n"
        
        response_message += "The optimized pipeline is ready to run!"
        
        return {
            "message": response_message,
            "status": "success",
            "optimizations": optimizations,
            "suggested_actions": ["run_pipeline", "review_changes"],
            "updated_context": optimized_context.model_dump()
        }
    
    async def _handle_general_question(
        self,
        message: str,
        intent: Intent,
        context: ConversationContext,
        similar_pipelines: List[Dict]
    ) -> Dict[str, Any]:
        """Handle general questions and conversations."""
        # Get conversation history for context
        history = await self._get_conversation_history(context.pipeline_id, limit=5)
        
        # Build conversational response
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add recent history
        for msg in reversed(history):
            if msg["role"] == "user":
                messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                messages.append({"role": "assistant", "content": msg["content"]})
        
        # Add current message with context
        messages.append({
            "role": "user",
            "content": f"Pipeline state: {json.dumps(context.model_dump(), default=str)}\n\nUser: {message}"
        })
        
        response = await self.llm.ainvoke(messages)
        
        return {
            "message": response.content,
            "status": "success",
            "suggested_actions": self._suggest_next_actions(context),
            "updated_context": context.model_dump()
        }
    
    async def _suggest_schema_fields(self, urls: List[str], description: str) -> Dict[str, str]:
        """Suggest schema fields based on URLs and description."""
        prompt = f"""Based on these URLs and the user's request, suggest data fields to extract:

URLs: {', '.join(urls[:3])}
Request: {description}

Suggest 5-8 relevant fields with their types. Be specific and practical.
Return as JSON: {{"field_name": "type", ...}}"""
        
        messages = [
            {"role": "system", "content": "You are a data extraction expert. Respond only in valid JSON."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self.llm.ainvoke(messages)
            result = json.loads(response.content.strip())
            
            # Ensure we return a dictionary
            if isinstance(result, dict):
                return result
            elif isinstance(result, list):
                # Convert list to dictionary
                fields_dict = {}
                for item in result:
                    if isinstance(item, dict):
                        if 'name' in item and 'type' in item:
                            fields_dict[item['name']] = item['type']
                        elif 'field' in item and 'type' in item:
                            fields_dict[item['field']] = item['type']
                        else:
                            # Use first key-value pair
                            for k, v in item.items():
                                fields_dict[k] = str(v)
                                break
                    elif isinstance(item, str):
                        fields_dict[item] = 'str'
                return fields_dict if fields_dict else self._get_fallback_schema()
            else:
                return self._get_fallback_schema()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to parse schema fields: {e}")
            return self._get_fallback_schema()
    
    def _get_fallback_schema(self) -> Dict[str, str]:
        """Get fallback schema when parsing fails."""
        return {
            "title": "str",
            "description": "str",
            "url": "str",
            "date": "str",
            "content": "str"
        }
    
    async def _generate_optimized_code(self, context: ConversationContext) -> str:
        """Generate optimized scraping code without Pydantic schemas."""
        
        # Create the extraction prompt
        field_descriptions = []
        for field_name in context.schema.keys():
            field_desc = field_name.replace('_', ' ').lower()
            field_descriptions.append(f"- {field_name}: {field_desc}")
        
        prompt_text = f"""Extract the following information from the webpage:
{chr(10).join(field_descriptions)}

Return the data as JSON with these exact field names."""
        
        code = f'''import asyncio
from typing import List, Dict, Any
from scrapegraph_py import AsyncClient
import json
from datetime import datetime

async def scrape_url(client: AsyncClient, url: str, prompt: str, max_retries: int = 3) -> Dict:
    """Scrape a single URL with retry logic."""
    for attempt in range(max_retries):
        try:
            # Use prompt-based extraction
            result = await client.smartscraper(
                website_url=url,
                user_prompt=prompt
            )
            
            # Extract data from API response
            if isinstance(result, dict) and 'result' in result:
                data = result.get('result', {{}})
            else:
                data = result if isinstance(result, dict) else {{"raw": str(result)}}
            
            return {{"success": True, "url": url, "data": data}}
            
        except Exception as e:
            if attempt == max_retries - 1:
                return {{"success": False, "url": url, "error": str(e)}}
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

async def scrape_pipeline(urls: List[str], api_key: str) -> Dict[str, Any]:
    """Execute the scraping pipeline."""
    start_time = datetime.now()
    
    # Define the extraction prompt
    prompt = """{prompt_text}"""
    
    print("🔍 Extraction Prompt:")
    print("-" * 40)
    print(prompt)
    print("-" * 40)
    
    async with AsyncClient(api_key=api_key) as client:
        # Configure for optimal performance
        client.max_concurrency = min(len(urls), 5)
        
        # Execute scraping tasks concurrently
        tasks = [scrape_url(client, url, prompt) for url in urls]
        results = await asyncio.gather(*tasks)
    
    # Calculate statistics
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    execution_time = (datetime.now() - start_time).total_seconds()
    
    return {{
        "results": results,
        "summary": {{
            "total_urls": len(urls),
            "successful": len(successful),
            "failed": len(failed),
            "execution_time": execution_time,
            "avg_time_per_url": execution_time / len(urls) if urls else 0
        }},
        "timestamp": datetime.now().isoformat()
    }}

# Configuration
URLS = {json.dumps(context.urls, indent=4)}

if __name__ == "__main__":
    # Your ScrapeGraphAI API key
    API_KEY = "your-api-key-here"  # Replace with your actual API key
    
    # Run the pipeline
    print(f"🚀 Starting scraping pipeline for {{len(URLS)}} URL(s)...")
    results = asyncio.run(scrape_pipeline(URLS, API_KEY))
    
    # Display results
    print(f"\\n✅ Pipeline Results:")
    print(f"   Successfully scraped: {{results['summary']['successful']}}/{{results['summary']['total_urls']}} URLs")
    print(f"   Execution time: {{results['summary']['execution_time']:.2f}} seconds")
    
    # Show extracted data
    for result in results['results']:
        print(f"\\n{{'='*60}}")
        print(f"URL: {{result['url']}}")
        if result['success']:
            print("Status: ✅ Success")
            print("Data:")
            print(json.dumps(result['data'], indent=2))
        else:
            print("Status: ❌ Failed")
            print(f"Error: {{result.get('error', 'Unknown error')}}")
'''
        
        return code
    
    async def _adapt_pipeline(self, template: Dict, context: ConversationContext) -> ConversationContext:
        """Adapt a template pipeline to current context."""
        # Merge template configuration with current context
        adapted = context.model_copy()
        
        # Use template schema if current is empty
        if not adapted.schema and template.get("schema"):
            adapted.schema = template["schema"]
        
        # Adapt code if available
        if template.get("code"):
            adapted.generated_code = template["code"]
            # Replace URLs in code
            if adapted.urls:
                adapted.generated_code = adapted.generated_code.replace(
                    str(template.get("urls", [])),
                    str(adapted.urls)
                )
        
        # Copy useful metadata
        adapted.metadata.update({
            "template_id": template.get("id"),
            "template_name": template.get("name"),
            "adapted_from": template.get("description")
        })
        
        return adapted
    
    async def _apply_optimizations(
        self,
        context: ConversationContext,
        optimizations: List[Dict]
    ) -> ConversationContext:
        """Apply suggested optimizations to context."""
        optimized = context.model_copy()
        
        for opt in optimizations:
            opt_type = opt.get("type")
            
            if opt_type == "add_concurrency":
                # Add concurrency to code
                if optimized.generated_code:
                    optimized.generated_code = optimized.generated_code.replace(
                        "max_concurrency = 1",
                        "max_concurrency = 5"
                    )
            
            elif opt_type == "add_retry":
                # Retry logic already in template
                pass
            
            elif opt_type == "optimize_schema":
                # Optimize schema fields
                if opt.get("fields"):
                    optimized.schema.update(opt["fields"])
        
        optimized.metadata["optimizations_applied"] = len(optimizations)
        
        return optimized
    
    def _suggest_next_actions(self, context: ConversationContext) -> List[str]:
        """Suggest next actions based on current state."""
        actions = []
        
        if not context.urls:
            actions.append("add_urls")
        elif not context.schema:
            actions.append("define_schema")
        elif not context.generated_code:
            actions.append("generate_code")
        else:
            actions.extend(["run_pipeline", "save_pipeline", "optimize_pipeline"])
        
        return actions
    
    async def _update_context(self, pipeline_id: str, context_data: Dict):
        """Update stored context."""
        context_key = f"context:{pipeline_id}"
        
        # Update timestamp
        context_data["last_updated"] = datetime.utcnow().isoformat()
        
        await self.redis_client.set(
            context_key,
            json.dumps(context_data, default=str),
            ex=self.conversation_ttl
        )
    
    async def save_pipeline(self, pipeline_id: str, name: str, description: str) -> Dict:
        """Save a pipeline for future reuse."""
        if not self.pipeline_repo:
            return {"status": "error", "message": "Pipeline repository not initialized"}
        
        context = await self._get_or_create_context(pipeline_id, None, None)
        
        saved_id = await self.pipeline_repo.save_pipeline({
            "name": name,
            "description": description,
            "urls": context.urls,
            "schema": context.schema,
            "code": context.generated_code,
            "metadata": context.metadata
        })
        
        return {
            "status": "success",
            "pipeline_id": saved_id,
            "message": f"Pipeline '{name}' saved successfully! You can now reuse it anytime."
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            await self.redis_client.close()


# Singleton instance
unified_agent = UnifiedScrapingAgent()