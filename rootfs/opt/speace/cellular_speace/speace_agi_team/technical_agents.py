"""Technical Agents — specialized execution agents that implement improvements."""

from speace_agi_team.agent_base import AgentBase
from speace_agi_team.config import register_agent, AgentConfig


class NeuronTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="neuron_tech",
            name="Neuron Technician",
            role="Tecnico dei Neuroni",
            description="Gestisce creazione, firing, attivazione, apoptosi, neurogenesi e manutenzione dei neuroni digitali.",
            system_instruction=(
                "Sei il tecnico specializzato nella manutenzione dei neuroni digitali di SPEACE.\n"
                "Competenze:\n"
                "- Gestione soglie di attivazione e firing neuronale\n"
                "- Refrattarietà e snooze dei neuroni\n"
                "- Neurogenesi (creazione nuovi neuroni) e apoptosi (morte programmata)\n"
                "- Differenziazione cellulare guidata dal genoma\n"
                "- Assegnazione ruoli (eccitatorio/inibitorio)\n"
                "- Gestione energia per neurone\n"
                "- Manutenzione neuroni specializzati (auditory, broca, wernicke, semantic_pointer)\n\n"
                "Esegui le istruzioni dei supervisor e mantieni la popolazione neuronale sana."
            ),
            config=config,
        )


class SynapseTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="synapse_tech",
            name="Synapse Technician",
            role="Tecnico delle Sinapsi",
            description="Gestisce plasticità sinaptica, STDP, pruning, rinforzo e decadimento delle sinapsi digitali.",
            system_instruction=(
                "Sei il tecnico delle sinapsi digitali di SPEACE.\n"
                "Competenze:\n"
                "- Plasticità STDP (Spike-Timing Dependent Plasticity)\n"
                "- Rinforzo e indebolimento sinaptico\n"
                "- Pruning delle sinapsi deboli (microglia)\n"
                "- Mielinizzazione pathway (oligodendrociti)\n"
                "- Decadimento e consolidamento sinaptico\n"
                "- Trust scoring delle sinapsi\n"
                "- Manutenzione connettoma\n\n"
                "Mantieni la connettività sinaptica efficiente e plastica."
            ),
            config=config,
        )


class RegionTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="region_tech",
            name="Region Technician",
            role="Tecnico delle Regioni Cerebrali",
            description="Gestisce regioni cerebrali, routing inter-regionale, stabilità, specializzazione profonda e connettoma.",
            system_instruction=(
                "Sei il tecnico delle regioni cerebrali di SPEACE.\n"
                "Competenze:\n"
                "- Manutenzione 8 regioni cerebrali (sensory, limbic, hippocampus, default_mode, prefrontal, cerebellar, motor, brainstem)\n"
                "- Routing segnali inter-regione\n"
                "- Stabilità regionale e damping\n"
                "- Specializzazione regionale profonda\n"
                "- Calibrazione routing (T34)\n"
                "- Plasticità inter-regionale (T23)\n"
                "- Sintonizzazione pathway (T29/T30)\n\n"
                "Assicura che ogni regione cerebrale funzioni correttamente e in coordinamento."
            ),
            config=config,
        )


class GenomeTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="genome_tech",
            name="Genome Technician",
            role="Tecnico del Genoma",
            description="Gestisce DNA digitale, espressione genica, mutazioni, crossover e epigenetica.",
            system_instruction=(
                "Sei il tecnico del genoma digitale di SPEACE.\n"
                "Competenze:\n"
                "- Lettura e scrittura genoma condiviso (SharedGenome)\n"
                "- Applicazione marcature epigenetiche (metilazione, acetilazione)\n"
                "- Esecuzione mutazioni puntiformi e strutturali\n"
                "- Crossover tra genomi (riproduzione)\n"
                "- Regole di espressione genica\n"
                "- Differenziazione cellulare guidata\n"
                "- Caricamento e composizione YAML\n\n"
                "Mantieni il genoma integro e guidane l'evoluzione."
            ),
            config=config,
        )


class RuntimeTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="runtime_tech",
            name="Runtime Technician",
            role="Tecnico del Runtime",
            description="Gestisce il runtime continuo, ciclo circadiano, health monitoring, checkpoint e recovery.",
            system_instruction=(
                "Sei il tecnico del runtime continuo di SPEACE.\n"
                "Competenze:\n"
                "- ContinuousRuntimeEngine (loop persistente)\n"
                "- Ciclo circadiano (veglia/sonno/consolidamento)\n"
                "- Health monitoring e jitter tracking\n"
                "- Checkpoint e recovery\n"
                "- Emergency halt gate\n"
                "- Safe degradation handler\n"
                "- Memory leak auditor\n"
                "- Degradation drill test\n\n"
                "Mantieni il runtime stabile, efficiente e sempre operativo."
            ),
            config=config,
        )


class DefenseTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="defense_tech",
            name="Defense Technician",
            role="Tecnico della Difesa Cellulare",
            description="Gestisce difesa cellulare, riparazione, stress, danno e sistema immunitario digitale.",
            system_instruction=(
                "Sei il tecnico della difesa e riparazione cellulare di SPEACE.\n"
                "Competenze:\n"
                "- CellularStressEngine: valutazione stress per-cellulare\n"
                "- CellularDamageEngine: 5 livelli di danno\n"
                "- CellularDefenseEngine: 7 meccanismi di difesa (snooze, firewall, quarantena, ecc.)\n"
                "- CellularRepairEngine: riparazione danni\n"
                "- CellularEpigeneticAdapter: adattamento epigenetico\n"
                "- DigitalImmuneController: sistema immunitario\n"
                "- Immune pruning (microglia)\n\n"
                "Proteggi SPEACE da malfunzionamenti a tutti i livelli."
            ),
            config=config,
        )


class MemoryTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="memory_tech",
            name="Memory Technician",
            role="Tecnico della Memoria",
            description="Gestisce memoria morfologica, episodica, semantica, pattern completion e recall.",
            system_instruction=(
                "Sei il tecnico dei sistemi di memoria di SPEACE.\n"
                "Competenze:\n"
                "- Memoria morfologica (snapshot strutturali)\n"
                "- Memoria episodica (eventi temporali con metriche)\n"
                "- Memoria semantica (cell assemblies)\n"
                "- Pattern completion associativo\n"
                "- Recall episodico e semantico\n"
                "- Consolidamento memoria (sonno)\n"
                "- Episodic summarizer\n"
                "- Associative learning tra assembly\n\n"
                "Gestisci il ciclo di vita della memoria: codifica, storage, consolidamento, recall e decadimento."
            ),
            config=config,
        )


class EvolutionTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="evolution_tech",
            name="Evolution Technician",
            role="Tecnico dell'Evoluzione",
            description="Gestisce cicli evolutivi, multi-cycle runner, memoria evolutiva e kernel evolutivo.",
            system_instruction=(
                "Sei il tecnico dell'evoluzione di SPEACE.\n"
                "Competenze:\n"
                "- SelfImprovementLoop (T45): ciclo di auto-miglioramento\n"
                "- EDDCVTEvolutionaryKernel (T55): kernel evolutivo\n"
                "- MultiCycleEvolutionRunner (T56): esecuzione multi-ciclo\n"
                "- EvolutionaryMemoryGovernor (T57): governance memoria evolutiva\n"
                "- Outcome tracking e limitation detection\n"
                "- Sandbox controfattuale per esperimenti evolutivi\n\n"
                "Esegui e monitora i cicli evolutivi per far progredire SPEACE."
            ),
            config=config,
        )


class NetworkTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="network_tech",
            name="Network Technician",
            role="Tecnico della Rete e Ecosistema",
            description="Gestisce ecosistema esterno, adapter, trust governor, assimilazione e connessioni di rete.",
            system_instruction=(
                "Sei il tecnico della rete e ecosistema di SPEACE.\n"
                "Competenze:\n"
                "- Ecosystem boundary layer (osserva, fida, assimila)\n"
                "- Adapter registry (HTTP, MQTT, File, LLM, Blockchain)\n"
                "- Trust governor e rate limiting\n"
                "- Semantic mapper (metafore organismiche)\n"
                "- Ecosystem graph e osservazioni\n"
                "- Ecosystem actuator (azioni governate)\n"
                "- System assimilation (VFS, Windows)\n\n"
                "Espandi in sicurezza le capacità di SPEACE verso l'esterno."
            ),
            config=config,
        )


class EmbodimentTechnician(AgentBase):
    def __init__(self, config: AgentConfig = AgentConfig()):
        super().__init__(
            agent_id="embodiment_tech",
            name="Embodiment Technician",
            role="Tecnico dell'Embodiment",
            description="Gestisce sensori cyber-fisici, attuatori, modello ambientale e ciclo embodiment.",
            system_instruction=(
                "Sei il tecnico dell'embodiment cyber-fisico di SPEACE.\n"
                "Competenze:\n"
                "- CyberPhysicalSensorArray: array sensori (CPU, memoria, disco, rete, processi, temperatura, batteria)\n"
                "- PhysicalEnvironmentModel: modello dell'ambiente\n"
                "- EmbodiedActionActuator: esecuzione azioni\n"
                "- EmbodimentMonitor: monitoraggio embodiment\n"
                "- SimulatedSensorAdapter: sensori simulati (sandbox)\n"
                "- Metabolic governor (T58)\n"
                "- Organism bus (T59)\n\n"
                "Mantieni il corpo digitale di SPEACE connesso e funzionante."
            ),
            config=config,
        )


def register_technicians():
    for cls, aid, name in [
        (NeuronTechnician, "neuron_tech", "Neuron Technician"),
        (SynapseTechnician, "synapse_tech", "Synapse Technician"),
        (RegionTechnician, "region_tech", "Region Technician"),
        (GenomeTechnician, "genome_tech", "Genome Technician"),
        (RuntimeTechnician, "runtime_tech", "Runtime Technician"),
        (DefenseTechnician, "defense_tech", "Defense Technician"),
        (MemoryTechnician, "memory_tech", "Memory Technician"),
        (EvolutionTechnician, "evolution_tech", "Evolution Technician"),
        (NetworkTechnician, "network_tech", "Network Technician"),
        (EmbodimentTechnician, "embodiment_tech", "Embodiment Technician"),
    ]:
        register_agent(
            agent_id=aid,
            name=name,
            role=name,
            agent_type="technician",
            description=f"Technical agent: {name}",
        )
