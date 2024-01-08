import os
from dotenv import load_dotenv

load_dotenv()

from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)

from speller_agent import SpellerAgentConfig
from vocode.streaming.telephony.config_manager.in_memory_config_manager import InMemoryConfigManager

from vocode.streaming.models.synthesizer import AzureSynthesizerConfig 
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig 
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.telephony import TwilioConfig

BASE_URL = os.environ["BASE_URL"]


async def main():
    config_manager = InMemoryConfigManager()

    synthesizer_config = AzureSynthesizerConfig(
        voice_name="es-CO-SalomeNeural",
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

    outbound_call = OutboundCall(
        base_url=BASE_URL,
        to_phone="+573104983987",
        from_phone="+15202239830",
        config_manager=config_manager,
        synthesizer_config=synthesizer_config,
        transcriber_config=transcriber_config,
        agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(text="Hola Camila, soy tu consciencia Siriana,como estas?"),
                prompt_preamble="Actua como un psicoanalista, y ten una consulta conmigo",
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
    )

    input("Press enter to start call...")
    await outbound_call.start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
