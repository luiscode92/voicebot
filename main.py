import logging
import os
from fastapi import FastAPI
from vocode.streaming.models.telephony import TwilioConfig
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TwilioInboundCallConfig,
    TelephonyServer,
)

from speller_agent import SpellerAgentFactory
import sys

from vocode.streaming.models.synthesizer import AzureSynthesizerConfig 
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig 

from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig, StreamElementsSynthesizerConfig
from dotenv import load_dotenv
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = InMemoryConfigManager()

BASE_URL = os.getenv("BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")


# Multilingual support for speech synthesis
# es-CO-SalomeNeural (Female)
# es-CO-GonzaloNeural (Male)
synthesizer_config = AzureSynthesizerConfig(
    voice_name="es-CO-GonzaloNeural",
    language_code="es-CO",
    sampling_rate=8000,
    audio_encoding="mulaw"
)

transcriber_config = DeepgramTranscriberConfig(
    language="es",
    sampling_rate=8000,
    audio_encoding="mulaw",
    chunk_size=1000
)

SYNTH_CONFIG = ElevenLabsSynthesizerConfig.from_telephone_output_device(
   api_key=os.getenv("ELEVEN_LABS_API_KEY") or "<your EL token>")



telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hola como estas?"),
                prompt_preamble="Have a pleasant conversation about life",
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
            synthesizer_config=synthesizer_config,
            transcriber_config=transcriber_config

        )
    ],
    agent_factory=SpellerAgentFactory(),
    logger=logger,
)

app.include_router(telephony_server.get_router())
