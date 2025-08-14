"""
Pattern Learning Service
Learns from scraping patterns to improve future suggestions and optimizations.
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import hashlib
from collections import defaultdict, Counter
from sqlalchemy import Column, String, JSON, DateTime, Float, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.config import settings
from app.services.database import Base


class ScrapingPattern(Base):
    """Model for learned scraping patterns."""
    __tablename__ = "scraping_patterns"
    
    id = Column(String, primary_key=True)
    domain = Column(String, nullable=False, index=True)
    data_type = Column(String, nullable=False, index=True)
    
    # Pattern details
    selectors_used = Column(JSON)  # CSS selectors or extraction patterns
    schema_pattern = Column(JSON)  # Common schema fields
    url_patterns = Column(JSON)  # URL structure patterns
    
    # Performance metrics
    success_rate = Column(Float, default=0.0)
    avg_extraction_time = Column(Float, default=0.0)
    total_executions = Column(Integer, default=0)
    
    # Optimization data
    optimizations = Column(JSON)  # Successful optimizations applied
    common_errors = Column(JSON)  # Common errors and solutions
    
    # Timestamps (renamed from Metadata to avoid conflicts)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)


class DomainKnowledge(Base):
    """Domain-specific knowledge base."""
    __tablename__ = "domain_knowledge"
    
    id = Column(String, primary_key=True)
    domain = Column(String, nullable=False, unique=True, index=True)
    
    # Knowledge data
    common_fields = Column(JSON)  # Commonly extracted fields
    field_mappings = Column(JSON)  # Field name variations
    extraction_rules = Column(JSON)  # Domain-specific rules
    
    # Structure information
    has_pagination = Column(Integer, default=0)  # Boolean as int
    has_infinite_scroll = Column(Integer, default=0)
    requires_javascript = Column(Integer, default=0)
    has_anti_scraping = Column(Integer, default=0)
    
    # Best practices
    optimal_delay = Column(Float, default=1.0)  # Seconds between requests
    max_concurrent = Column(Integer, default=3)
    retry_strategy = Column(JSON)
    
    # Statistics
    total_scraped = Column(Integer, default=0)
    avg_success_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PatternLearner:
    """Service for learning from scraping patterns and improving suggestions."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pattern_cache = {}
        self.domain_cache = {}
        self.learning_threshold = 5  # Minimum executions before learning
    
    async def initialize(self):
        """Initialize the pattern learner."""
        # Connect to Redis for caching
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Load frequently used patterns into cache
        await self._load_pattern_cache()
    
    async def _load_pattern_cache(self):
        """Load frequently used patterns into memory cache."""
        # This would load from database in production
        # For now, initialize with common patterns
        self.pattern_cache = {
            "ecommerce": {
                "common_fields": ["title", "price", "description", "availability", "rating", "image"],
                "selectors": {
                    "title": ["h1", ".product-title", "[itemprop='name']"],
                    "price": [".price", "[itemprop='price']", ".product-price"],
                    "description": [".description", "[itemprop='description']", ".product-description"]
                }
            },
            "news": {
                "common_fields": ["title", "content", "author", "date", "category", "tags"],
                "selectors": {
                    "title": ["h1", ".article-title", "[itemprop='headline']"],
                    "content": ["article", ".article-content", "[itemprop='articleBody']"],
                    "author": [".author", "[itemprop='author']", ".by-line"]
                }
            },
            "weather": {
                "common_fields": ["temperature", "humidity", "wind_speed", "conditions", "forecast"],
                "selectors": {
                    "temperature": [".temperature", ".temp", "[data-testid='temperature']"],
                    "humidity": [".humidity", "[data-testid='humidity']"],
                    "wind_speed": [".wind", "[data-testid='wind']"]
                }
            }
        }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or "unknown"
    
    def _classify_data_type(self, schema: Dict[str, Any]) -> str:
        """Classify the type of data being scraped based on schema."""
        field_names = set(key.lower() for key in schema.keys())
        
        # Classification rules
        if any(field in field_names for field in ["price", "cost", "availability", "stock"]):
            return "ecommerce"
        elif any(field in field_names for field in ["article", "content", "author", "publish"]):
            return "news"
        elif any(field in field_names for field in ["temperature", "weather", "humidity", "wind"]):
            return "weather"
        elif any(field in field_names for field in ["job", "salary", "experience", "company"]):
            return "jobs"
        else:
            return "general"
    
    async def learn_from_interaction(
        self,
        intent: Any,  # Can be Intent object or Dict
        context: Any,  # Can be ConversationContext or Dict
        response: Dict
    ) -> None:
        """Learn from a user interaction."""
        # Handle Intent object or dictionary
        if hasattr(intent, 'primary_intent'):  # Intent object
            intent_data = {
                "primary_intent": intent.primary_intent,
                "confidence": intent.confidence
            }
        else:  # Dictionary
            intent_data = {
                "primary_intent": intent.get("primary_intent"),
                "confidence": intent.get("confidence", 0)
            }
        
        # Handle ConversationContext object or dictionary
        if hasattr(context, 'urls'):  # ConversationContext object
            context_data = {
                "urls": context.urls,
                "schema": context.schema
            }
        else:  # Dictionary
            context_data = {
                "urls": context.get("urls", []),
                "schema": context.get("schema", {})
            }
        
        # Extract learning data
        learning_data = {
            "intent": intent_data["primary_intent"],
            "confidence": intent_data["confidence"],
            "urls": context_data["urls"],
            "schema": context_data["schema"],
            "success": response.get("status") == "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis for batch processing
        learning_key = f"learning:interaction:{datetime.utcnow().date()}"
        await self.redis_client.lpush(learning_key, json.dumps(learning_data))
        await self.redis_client.expire(learning_key, 86400 * 30)  # 30 days
        
        # Process if we have enough data
        interactions = await self.redis_client.llen(learning_key)
        if interactions >= self.learning_threshold:
            await self._process_learning_batch(learning_key)
    
    async def learn_from_execution(
        self,
        context,
        results: List[Dict]
    ) -> None:
        """Learn from pipeline execution results."""
        if not results:
            return
        
        # Handle both dict and Pydantic model
        if hasattr(context, 'schema'):
            # It's a Pydantic model
            schema = context.schema
        else:
            # It's a dict
            schema = context.get("schema", {})
        
        # Analyze results
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        
        # Extract patterns from successful scrapes
        if successful:
            for url_result in successful[:3]:  # Sample first 3
                domain = self._extract_domain(url_result.get("url", ""))
                data_type = self._classify_data_type(schema)
                
                pattern_data = {
                    "domain": domain,
                    "data_type": data_type,
                    "schema": schema,
                    "success": True,
                    "url": url_result.get("url"),
                    "extracted_fields": list(url_result.get("data", {}).keys()) if url_result.get("data") else []
                }
                
                await self._update_pattern(pattern_data)
        
        # Learn from failures
        if failed:
            for url_result in failed:
                error_data = {
                    "domain": self._extract_domain(url_result.get("url", "")),
                    "error": url_result.get("error", "Unknown error"),
                    "schema": schema,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                await self._record_error_pattern(error_data)
    
    async def _update_pattern(self, pattern_data: Dict) -> None:
        """Update pattern database with new learning."""
        pattern_key = f"pattern:{pattern_data['domain']}:{pattern_data['data_type']}"
        
        # Store in Redis for aggregation
        await self.redis_client.hset(
            pattern_key,
            mapping={
                "last_success": datetime.utcnow().isoformat(),
                "success_count": await self.redis_client.hincrby(pattern_key, "success_count", 1),
                "schema": json.dumps(pattern_data["schema"]),
                "extracted_fields": json.dumps(pattern_data.get("extracted_fields", []))
            }
        )
        
        await self.redis_client.expire(pattern_key, 86400 * 90)  # 90 days
    
    async def _record_error_pattern(self, error_data: Dict) -> None:
        """Record error patterns for learning."""
        error_key = f"errors:{error_data['domain']}"
        
        # Store error pattern
        await self.redis_client.lpush(error_key, json.dumps(error_data))
        await self.redis_client.ltrim(error_key, 0, 99)  # Keep last 100 errors
        await self.redis_client.expire(error_key, 86400 * 30)  # 30 days
    
    async def suggest_optimizations(self, context) -> List[Dict]:
        """Suggest optimizations based on learned patterns."""
        optimizations = []
        
        # Handle both dict and Pydantic model
        if hasattr(context, 'urls'):
            # It's a Pydantic model
            urls = context.urls
            schema = context.schema
        else:
            # It's a dict
            urls = context.get("urls", [])
            schema = context.get("schema", {})
        
        if not urls:
            return optimizations
        
        # Extract domain and data type
        domain = self._extract_domain(urls[0]) if urls else "unknown"
        data_type = self._classify_data_type(schema)
        
        # Check domain knowledge
        domain_knowledge = await self._get_domain_knowledge(domain)
        
        # Optimization 1: Concurrency settings
        if len(urls) > 5:
            if domain_knowledge and domain_knowledge.get("max_concurrent"):
                optimizations.append({
                    "type": "add_concurrency",
                    "suggestion": f"Use {domain_knowledge['max_concurrent']} concurrent requests for {domain}",
                    "improvement": "2-3x faster execution",
                    "confidence": 0.9
                })
            else:
                optimizations.append({
                    "type": "add_concurrency",
                    "suggestion": "Enable concurrent processing for multiple URLs",
                    "improvement": "Faster execution",
                    "confidence": 0.8
                })
        
        # Optimization 2: Retry strategy
        if domain_knowledge and domain_knowledge.get("retry_strategy"):
            optimizations.append({
                "type": "add_retry",
                "suggestion": "Add exponential backoff retry strategy",
                "improvement": "Better reliability",
                "confidence": 0.85
            })
        
        # Optimization 3: Schema optimization
        pattern = self.pattern_cache.get(data_type, {})
        if pattern and pattern.get("common_fields"):
            missing_fields = set(pattern["common_fields"]) - set(schema.keys())
            if missing_fields:
                optimizations.append({
                    "type": "optimize_schema",
                    "suggestion": f"Consider adding fields: {', '.join(missing_fields)}",
                    "fields": {field: "str" for field in missing_fields},
                    "improvement": "More comprehensive data extraction",
                    "confidence": 0.7
                })
        
        # Optimization 4: JavaScript rendering
        if domain_knowledge and domain_knowledge.get("requires_javascript"):
            optimizations.append({
                "type": "enable_js",
                "suggestion": "Enable JavaScript rendering for dynamic content",
                "improvement": "Access to dynamically loaded data",
                "confidence": 0.9
            })
        
        # Optimization 5: Rate limiting
        if domain_knowledge and domain_knowledge.get("optimal_delay", 0) > 0:
            optimizations.append({
                "type": "add_delay",
                "suggestion": f"Add {domain_knowledge['optimal_delay']}s delay between requests",
                "improvement": "Avoid rate limiting",
                "confidence": 0.8
            })
        
        # Sort by confidence
        optimizations.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return optimizations
    
    async def _get_domain_knowledge(self, domain: str) -> Optional[Dict]:
        """Get domain-specific knowledge."""
        # Check cache first
        if domain in self.domain_cache:
            return self.domain_cache[domain]
        
        # Check Redis
        domain_key = f"domain:knowledge:{domain}"
        knowledge = await self.redis_client.hgetall(domain_key)
        
        if knowledge:
            # Parse JSON fields
            for key in ["retry_strategy", "common_fields", "field_mappings"]:
                if key in knowledge:
                    try:
                        knowledge[key] = json.loads(knowledge[key])
                    except:
                        pass
            
            # Convert string booleans
            for key in ["has_pagination", "has_infinite_scroll", "requires_javascript", "has_anti_scraping"]:
                if key in knowledge:
                    knowledge[key] = knowledge[key] == "1" or knowledge[key] == "true"
            
            # Convert numeric fields
            for key in ["optimal_delay", "max_concurrent", "avg_success_rate"]:
                if key in knowledge:
                    try:
                        knowledge[key] = float(knowledge[key]) if "." in knowledge[key] else int(knowledge[key])
                    except:
                        pass
            
            self.domain_cache[domain] = knowledge
            return knowledge
        
        return None
    
    async def _process_learning_batch(self, batch_key: str) -> None:
        """Process a batch of learning data."""
        # Get all interactions
        interactions = await self.redis_client.lrange(batch_key, 0, -1)
        
        if not interactions:
            return
        
        # Parse interactions
        parsed = [json.loads(i) for i in interactions]
        
        # Aggregate patterns
        patterns = defaultdict(list)
        for interaction in parsed:
            if interaction.get("urls") and interaction.get("schema"):
                domain = self._extract_domain(interaction["urls"][0])
                data_type = self._classify_data_type(interaction["schema"])
                key = f"{domain}:{data_type}"
                patterns[key].append(interaction)
        
        # Update pattern database
        for pattern_key, pattern_list in patterns.items():
            if len(pattern_list) >= 3:  # Minimum threshold
                domain, data_type = pattern_key.split(":", 1)
                
                # Calculate statistics
                success_rate = sum(1 for p in pattern_list if p.get("success")) / len(pattern_list)
                
                # Extract common schema fields
                all_fields = []
                for p in pattern_list:
                    all_fields.extend(p.get("schema", {}).keys())
                
                common_fields = [
                    field for field, count in Counter(all_fields).items()
                    if count >= len(pattern_list) * 0.5  # Field appears in 50%+ of patterns
                ]
                
                # Update domain knowledge
                await self._update_domain_knowledge(domain, {
                    "data_type": data_type,
                    "success_rate": success_rate,
                    "common_fields": common_fields,
                    "sample_size": len(pattern_list)
                })
        
        # Clear processed batch
        await self.redis_client.delete(batch_key)
    
    async def _update_domain_knowledge(self, domain: str, knowledge: Dict) -> None:
        """Update domain knowledge base."""
        domain_key = f"domain:knowledge:{domain}"
        
        # Get existing knowledge
        existing = await self.redis_client.hgetall(domain_key)
        
        # Update with new knowledge
        updates = {}
        
        if "common_fields" in knowledge:
            # Merge common fields
            existing_fields = json.loads(existing.get("common_fields", "[]"))
            new_fields = list(set(existing_fields + knowledge["common_fields"]))
            updates["common_fields"] = json.dumps(new_fields)
        
        if "success_rate" in knowledge:
            # Update success rate with weighted average
            old_rate = float(existing.get("avg_success_rate", 0))
            old_count = int(existing.get("sample_count", 0))
            new_rate = knowledge["success_rate"]
            new_count = knowledge.get("sample_size", 1)
            
            avg_rate = (old_rate * old_count + new_rate * new_count) / (old_count + new_count)
            updates["avg_success_rate"] = str(avg_rate)
            updates["sample_count"] = str(old_count + new_count)
        
        updates["last_updated"] = datetime.utcnow().isoformat()
        
        # Store updates
        if updates:
            await self.redis_client.hset(domain_key, mapping=updates)
            await self.redis_client.expire(domain_key, 86400 * 180)  # 180 days
            
            # Clear cache
            if domain in self.domain_cache:
                del self.domain_cache[domain]
    
    async def get_field_suggestions(
        self,
        domain: str,
        data_type: str
    ) -> List[Dict]:
        """Get field suggestions for a domain and data type."""
        suggestions = []
        
        # Check pattern cache
        pattern = self.pattern_cache.get(data_type, {})
        if pattern and pattern.get("common_fields"):
            for field in pattern["common_fields"]:
                suggestions.append({
                    "field": field,
                    "type": "str",  # Default type
                    "required": field in ["title", "price", "name"],
                    "description": f"Extract {field} information"
                })
        
        # Check domain knowledge
        domain_knowledge = await self._get_domain_knowledge(domain)
        if domain_knowledge and domain_knowledge.get("common_fields"):
            for field in domain_knowledge["common_fields"]:
                if not any(s["field"] == field for s in suggestions):
                    suggestions.append({
                        "field": field,
                        "type": "str",
                        "required": False,
                        "description": f"Domain-specific {field} field"
                    })
        
        return suggestions
    
    async def get_extraction_tips(self, domain: str) -> List[str]:
        """Get extraction tips for a specific domain."""
        tips = []
        
        domain_knowledge = await self._get_domain_knowledge(domain)
        
        if domain_knowledge:
            if domain_knowledge.get("requires_javascript"):
                tips.append("This site requires JavaScript rendering for dynamic content")
            
            if domain_knowledge.get("has_pagination"):
                tips.append("The site has pagination - consider extracting page links")
            
            if domain_knowledge.get("has_anti_scraping"):
                tips.append("This site has anti-scraping measures - use appropriate delays and headers")
            
            if domain_knowledge.get("optimal_delay", 0) > 0:
                tips.append(f"Recommended delay between requests: {domain_knowledge['optimal_delay']}s")
            
            if domain_knowledge.get("avg_success_rate", 0) < 0.5:
                tips.append("This domain has a low success rate - consider using different extraction methods")
        
        return tips
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.redis_client:
            await self.redis_client.close()