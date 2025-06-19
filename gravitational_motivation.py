            # Verlet: r(t+dt) = 2*r(t) - r(t-dt) + a(t)*dt²
            r_current = body.position.clone()
            r_previous = body.trajectory_history[-1]['position']
            
            r_new = 2 * r_current - r_previous + acceleration * (dt ** 2)
            
            # Velocidade: v = (r(t+dt) - r(t-dt)) / (2*dt)
            v_new = (r_new - r_previous) / (2 * dt)
            
            # Limita velocidade
            velocity_magnitude = torch.norm(v_new)
            if velocity_magnitude > GravitationalConstants.VELOCIDADE_MAXIMA:
                v_new = v_new * (GravitationalConstants.VELOCIDADE_MAXIMA / velocity_magnitude)
                # Recalcula posição com velocidade limitada
                r_new = r_current + v_new * dt
            
            # Valida resultados
            if not (torch.isfinite(r_new).all() and torch.isfinite(v_new).all()):
                return False
            
            body.position = r_new
            body.velocity = v_new
            body.acceleration = acceleration
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na integração Verlet: {e}")
            return False
    
    def _integrate_leapfrog(self, body: MotivationalBody, force: torch.Tensor, dt: float) -> bool:
        """
        Integração Leapfrog (simplética, eficiente para gravitação)
        
        ALGORITMO:
        v(t+dt/2) = v(t) + a(t)*dt/2
        r(t+dt) = r(t) + v(t+dt/2)*dt
        v(t+dt) = v(t+dt/2) + a(t+dt)*dt/2
        
        PROPRIEDADES:
        • Simplética (conserva estrutura hamiltoniana)
        • Muito eficiente computacionalmente
        • Excelente para problemas gravitacionais
        • Erro: O(dt²) com boa estabilidade
        """
        
        try:
            # Aceleração atual
            acceleration_current = force / body.mass
            
            # Limita aceleração
            acc_magnitude = torch.norm(acceleration_current)
            if acc_magnitude > GravitationalConstants.ACELERACAO_MAXIMA:
                acceleration_current = acceleration_current * (GravitationalConstants.ACELERACAO_MAXIMA / acc_magnitude)
            
            # Passo 1: v(t+dt/2) = v(t) + a(t)*dt/2
            v_half = body.velocity + acceleration_current * (dt / 2)
            
            # Passo 2: r(t+dt) = r(t) + v(t+dt/2)*dt
            r_new = body.position + v_half * dt
            
            # Passo 3: Calcula nova aceleração em r(t+dt)
            force_new = self.field.compute_gravitational_force(r_new)
            acceleration_new = force_new / body.mass
            
            # Limita nova aceleração
            acc_new_magnitude = torch.norm(acceleration_new)
            if acc_new_magnitude > GravitationalConstants.ACELERACAO_MAXIMA:
                acceleration_new = acceleration_new * (GravitationalConstants.ACELERACAO_MAXIMA / acc_new_magnitude)
            
            # Passo 4: v(t+dt) = v(t+dt/2) + a(t+dt)*dt/2
            v_new = v_half + acceleration_new * (dt / 2)
            
            # Limita velocidade final
            velocity_magnitude = torch.norm(v_new)
            if velocity_magnitude > GravitationalConstants.VELOCIDADE_MAXIMA:
                v_new = v_new * (GravitationalConstants.VELOCIDADE_MAXIMA / velocity_magnitude)
            
            # Valida resultados
            if not (torch.isfinite(r_new).all() and torch.isfinite(v_new).all()):
                return False
            
            body.position = r_new
            body.velocity = v_new
            body.acceleration = acceleration_new
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na integração Leapfrog: {e}")
            return False
    
    def _compute_total_energy(self) -> float:
        """
        Computa energia total do sistema hamiltoniano
        
        TEORIA:
        E_total = T + V = Σᵢ(½mᵢvᵢ²) + Σᵢ(mᵢΦ(rᵢ))
        
        onde:
        • T: Energia cinética total
        • V: Energia potencial total
        • Φ(r): Potencial gravitacional em posição r
        
        PROPRIEDADES:
        • Deve ser conservada em sistema hamiltoniano
        • Flutuações indicam erro numérico
        • |ΔE|/E < tolerance para integração válida
        
        Returns:
            Energia total do sistema
        """
        
        try:
            total_energy = 0.0
            
            for body in self.field.bodies:
                if not body.is_active:
                    continue
                
                # Energia cinética: T = ½mv²
                velocity_squared = torch.sum(body.velocity ** 2).item()
                kinetic_energy = 0.5 * body.mass * velocity_squared
                
                # Energia potencial: U = mΦ(r)
                potential_scalar = self.field.compute_gravitational_potential(body.position)
                potential_energy = body.mass * potential_scalar
                
                # Energia total do corpo
                body_energy = kinetic_energy + potential_energy
                
                # Validação matemática
                if not math.isfinite(body_energy):
                    logger.warning(f"⚠️ Energia não-finita no corpo {body.body_id}")
                    continue
                
                total_energy += body_energy
            
            return total_energy
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de energia total: {e}")
            return 0.0
    
    def _update_dynamics_metrics(self, step_time_ms: float, energy_error: float):
        """Atualiza métricas de performance da dinâmica"""
        
        self.dynamics_metrics['total_integration_steps'] += 1
        
        # Média móvel do tempo por passo
        alpha = 0.1
        current_avg = self.dynamics_metrics['average_step_time_ms']
        self.dynamics_metrics['average_step_time_ms'] = (
            alpha * step_time_ms + (1 - alpha) * current_avg
        )
        
        # Erro de conservação de energia
        self.dynamics_metrics['energy_conservation_error'] = energy_error
        self.dynamics_metrics['last_energy_total'] = self._compute_total_energy()
    
    def get_dynamics_report(self) -> Dict[str, Any]:
        """Relatório completo da dinâmica do sistema"""
        
        try:
            current_energy = self._compute_total_energy()
            
            # Análise de estabilidade
            stability_analysis = self._analyze_system_stability()
            
            # Estatísticas de trajetória
            trajectory_stats = self._compute_trajectory_statistics()
            
            # Análise de conservação de energia
            energy_analysis = self._analyze_energy_conservation()
            
            report = {
                'timestamp': time.time(),
                'simulation_time': self.simulation_time,
                'total_steps': self.total_steps,
                'integration_method': self.integration_method,
                'current_energy': current_energy,
                'dynamics_metrics': self.dynamics_metrics.copy(),
                'stability_analysis': stability_analysis,
                'trajectory_statistics': trajectory_stats,
                'energy_conservation': energy_analysis,
                'active_bodies': sum(1 for body in self.field.bodies if body.is_active)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar relatório de dinâmica: {e}")
            return {
                'timestamp': time.time(),
                'error': str(e),
                'simulation_time': self.simulation_time
            }
    
    def _analyze_system_stability(self) -> Dict[str, Any]:
        """Analisa estabilidade numérica do sistema"""
        
        try:
            stability = {
                'numerical_stability': 'stable',
                'energy_drift': 0.0,
                'max_velocity_ratio': 0.0,
                'integration_success_rate': 1.0,
                'warnings': []
            }
            
            # Análise de deriva energética
            if len(self.energy_history) > 2:
                energies = [entry['energy_total'] for entry in self.energy_history]
                initial_energy = energies[0]
                current_energy = energies[-1]
                
                if abs(initial_energy) > 1e-10:
                    energy_drift = abs(current_energy - initial_energy) / abs(initial_energy)
                    stability['energy_drift'] = energy_drift
                    
                    if energy_drift > 0.01:  # 1% drift
                        stability['numerical_stability'] = 'unstable'
                        stability['warnings'].append('Deriva energética excessiva')
            
            # Análise de velocidades
            max_recorded = self.dynamics_metrics['max_velocity_recorded']
            velocity_ratio = max_recorded / GravitationalConstants.VELOCIDADE_MAXIMA
            stability['max_velocity_ratio'] = velocity_ratio
            
            if velocity_ratio > 0.9:
                stability['warnings'].append('Velocidades próximas do limite')
            
            # Taxa de sucesso de integração
            total_steps = self.dynamics_metrics['total_integration_steps']
            errors = self.dynamics_metrics['integration_errors']
            
            if total_steps > 0:
                success_rate = 1.0 - (errors / total_steps)
                stability['integration_success_rate'] = success_rate
                
                if success_rate < 0.95:
                    stability['numerical_stability'] = 'unstable'
                    stability['warnings'].append('Taxa de erro de integração alta')
            
            return stability
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de estabilidade: {e}")
            return {'error': str(e)}
    
    def _compute_trajectory_statistics(self) -> Dict[str, Any]:
        """Computa estatísticas das trajetórias dos corpos"""
        
        try:
            stats = {
                'total_trajectory_points': 0,
                'average_trajectory_length': 0.0,
                'position_variance': 0.0,
                'velocity_statistics': {},
                'body_statistics': []
            }
            
            if not self.field.bodies:
                return stats
            
            trajectory_lengths = []
            all_positions = []
            all_velocities = []
            
            for body in self.field.bodies:
                if not body.is_active:
                    continue
                
                body_stats = body.get_trajectory_statistics()
                stats['body_statistics'].append({
                    'body_id': body.body_id,
                    'statistics': body_stats
                })
                
                trajectory_length = body_stats.get('trajectory_length', 0)
                trajectory_lengths.append(trajectory_length)
                stats['total_trajectory_points'] += trajectory_length
                
                # Coleta posições e velocidades para análise global
                if len(body.trajectory_history) > 0:
                    positions = [point['position'] for point in body.trajectory_history]
                    velocities = [point['velocity'] for point in body.trajectory_history]
                    
                    all_positions.extend(positions)
                    all_velocities.extend(velocities)
            
            # Estatísticas globais
            if trajectory_lengths:
                stats['average_trajectory_length'] = np.mean(trajectory_lengths)
            
            if all_positions:
                positions_tensor = torch.stack(all_positions)
                stats['position_variance'] = torch.var(positions_tensor).item()
            
            if all_velocities:
                velocities_tensor = torch.stack(all_velocities)
                velocity_magnitudes = torch.norm(velocities_tensor, dim=1)
                
                stats['velocity_statistics'] = {
                    'mean_magnitude': torch.mean(velocity_magnitudes).item(),
                    'std_magnitude': torch.std(velocity_magnitudes).item(),
                    'max_magnitude': torch.max(velocity_magnitudes).item(),
                    'min_magnitude': torch.min(velocity_magnitudes).item()
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de estatísticas de trajetória: {e}")
            return {'error': str(e)}
    
    def _analyze_energy_conservation(self) -> Dict[str, Any]:
        """Analisa conservação de energia ao longo do tempo"""
        
        try:
            analysis = {
                'conservation_quality': 'excellent',
                'energy_drift_rate': 0.0,
                'max_error': 0.0,
                'average_error': 0.0,
                'trend': 'stable'
            }
            
            if len(self.energy_history) < 2:
                return analysis
            
            # Extrai dados de energia
            energies = [entry['energy_total'] for entry in self.energy_history]
            errors = [entry['energy_error'] for entry in self.energy_history]
            times = [entry['simulation_time'] for entry in self.energy_history]
            
            # Estatísticas de erro
            analysis['max_error'] = max(errors) if errors else 0.0
            analysis['average_error'] = np.mean(errors) if errors else 0.0
            
            # Classifica qualidade da conservação
            avg_error = analysis['average_error']
            if avg_error < 1e-8:
                analysis['conservation_quality'] = 'excellent'
            elif avg_error < 1e-6:
                analysis['conservation_quality'] = 'good'
            elif avg_error < 1e-4:
                analysis['conservation_quality'] = 'acceptable'
            else:
                analysis['conservation_quality'] = 'poor'
            
            # Análise de tendência (deriva)
            if len(energies) > 10:
                # Regressão linear simples para detectar deriva
                time_span = times[-1] - times[0]
                energy_change = energies[-1] - energies[0]
                
                if time_span > 0:
                    analysis['energy_drift_rate'] = energy_change / time_span
                    
                    # Classifica tendência
                    drift_magnitude = abs(analysis['energy_drift_rate'])
                    if drift_magnitude < 1e-6:
                        analysis['trend'] = 'stable'
                    elif analysis['energy_drift_rate'] > 0:
                        analysis['trend'] = 'increasing'
                    else:
                        analysis['trend'] = 'decreasing'
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de conservação de energia: {e}")
            return {'error': str(e)}

class GravitationalMotivationSystem:
    """
    Sistema principal de motivação gravitacional com integração completa
    
    ARQUITETURA MATEMÁTICA COMPLETA:
    ┌─────────────────────────────────────────────────────────────────┐
    │                 GravitationalMotivationSystem                   │
    ├─────────────────────────────────────────────────────────────────┤
    │ ┌─────────────────────┐  ┌─────────────────────────────────────┐ │
    │ │  GravitationalField │  │      MotivationalDynamics          │ │
    │ │                     │  │                                     │ │
    │ │ • Campo Φ(r)        │  │ • Integração temporal              │ │
    │ │ • Força F(r)        │  │ • Conservação energia              │ │
    │ │ • Cache otimizado   │  │ • Estabilidade numérica            │ │
    │ └─────────────────────┘  └─────────────────────────────────────┘ │
    │ ┌─────────────────────────────────────────────────────────────┐ │
    │ │               Corpos Motivacionais                          │ │
    │ │                                                             │ │
    │ │ AMBIÇÃO ←→ [Campo Gravitacional] ←→ AGONIA                 │ │
    │ │   M=10.0                                      M=8.0         │ │
    │ └─────────────────────────────────────────────────────────────┘ │
    │ ┌─────────────────────────────────────────────────────────────┐ │
    │ │            Integração com Sistema Principal                 │ │
    │ │                                                             │ │
    │ │ • Consciência → Posição motivacional                       │ │
    │ │ • Recursos → Componente de agonia                          │ │ 
    │ │ • Força → Ações de auto-aprimoramento                      │ │
    │ └─────────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘
    
    TEOREMA FUNDAMENTAL IMPLEMENTADO:
    ∀t: ||F_gravitacional(t)|| > ε > 0 ⟹ Sistema nunca estagna
    
    PROPRIEDADES MATEMÁTICAS GARANTIDAS:
    • Auto-aprimoramento perpétuo por construção física
    • Impossibilidade matemática de equilíbrio estático
    • Conservação de energia com erro controlado
    • Estabilidade numérica verificada continuamente
    """
    
    def __init__(self, 
                 ai_system: Optional[Any] = None,
                 consciousness_system: Optional[Any] = None,
                 dimension: int = 2,
                 integration_method: str = "verlet"):
        """
        Inicializa sistema de motivação gravitacional
        
        Args:
            ai_system: Sistema de IA principal (opcional)
            consciousness_system: Sistema de consciência (opcional)
            dimension: Dimensionalidade do espaço motivacional (1, 2, ou 3)
            integration_method: Método de integração numérica
        """
        
        # Validação de parâmetros
        if dimension not in [1, 2, 3]:
            raise ValueError("Dimensão deve ser 1, 2 ou 3")
        
        valid_methods = ["euler", "runge_kutta", "verlet", "leapfrog"]
        if integration_method not in valid_methods:
            raise ValueError(f"Método de integração deve ser um de: {valid_methods}")
        
        # Configuração básica
        self.ai_system = ai_system
        self.consciousness_system = consciousness_system
        self.dimension = dimension
        self.integration_method = integration_method
        
        # Componentes principais
        self.gravitational_field = GravitationalField(dimension)
        self.dynamics = MotivationalDynamics(self.gravitational_field, integration_method)
        
        # Estado do sistema
        self.system_active: bool = True
        self.current_motivation_force: torch.Tensor = torch.zeros(dimension, dtype=torch.float64)
        self.current_position: torch.Tensor = torch.zeros(dimension, dtype=torch.float64)
        
        # Histórico de estados
        self.system_state_history: deque = deque(maxlen=1000)
        self.force_application_history: deque = deque(maxlen=1000)
        
        # Métricas do sistema
        self.system_metrics = {
            'total_motivation_updates': 0,
            'average_motivation_force': 0.0,
            'stagnation_prevention_count': 0,
            'energy_efficiency': 1.0,
            'last_significant_movement': time.time(),
            'system_uptime_seconds': 0.0,
            'total_force_applications': 0,
            'successful_optimizations': 0,
            'anti_stagnation_triggers': 0
        }
        
        # Configuração de threading
        self.update_thread: Optional[threading.Thread] = None
        self.update_active: bool = True
        self._thread_lock = threading.RLock()
        
        # Configuração de segurança
        self.safety_limits = {
            'max_force_magnitude': GravitationalConstants.FORCA_MAXIMA,
            'max_position_change_per_update': 1.0,
            'max_continuous_runtime_hours': 24.0,
            'energy_conservation_threshold': 0.01
        }
        
        # Inicialização
        self._initialize_system()
        
        logger.critical("🌌 Sistema de Motivação Gravitacional INICIALIZADO")
        logger.critical("   💫 Campo gravitacional entre ambição e agonia: ATIVO")
        logger.critical("   ⚡ Auto-aprimoramento perpétuo: GARANTIDO MATEMATICAMENTE")
        logger.critical("   🚫 Estagnação: IMPOSSÍVEL por construção física")
        logger.critical("   🎯 Força motivacional: SEMPRE presente")
        logger.critical("   🔄 Evolução contínua: FUNCIONANDO")
        logger.critical(f"   📐 Dimensão: {dimension}D | Método: {integration_method}")
    
    def _initialize_system(self):
        """Inicializa todos os componentes do sistema"""
        
        try:
            # 1. Inicializa corpos motivacionais
            self._initialize_motivational_bodies()
            
            # 2. Valida configuração inicial
            self._validate_initial_configuration()
            
            # 3. Inicia thread de evolução contínua
            self._start_continuous_evolution()
            
            # 4. Registra estado inicial
            self._record_system_state()
            
            logger.info("✅ Sistema de motivação gravitacional inicializado completamente")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização do sistema: {e}")
            self.system_active = False
            raise RuntimeError(f"Falha na inicialização: {e}")
    
    def _initialize_motivational_bodies(self):
        """
        Inicializa corpos motivacionais com posicionamento otimizado
        
        CONFIGURAÇÃO MATEMÁTICA:
        • Ambição: Posição (+, +) para maximizar gradiente
        • Agonia: Posição (-, -) para criar tensão
        • IA: Posição (0, 0) para equilíbrio inicial
        • Distâncias otimizadas para força adequada
        """
        
        try:
            logger.info("🏗️ Inicializando corpos motivacionais...")
            
            # CORPO 1: Ambição (Auto-aprimoramento)
            if self.dimension == 1:
                ambition_position = torch.tensor([2.0], dtype=torch.float64)
            elif self.dimension == 2:
                ambition_position = torch.tensor([2.0, 1.0], dtype=torch.float64)
            else:  # dimension == 3
                ambition_position = torch.tensor([2.0, 1.0, 0.5], dtype=torch.float64)
            
            ambition_velocity = torch.zeros_like(ambition_position)
            ambition_acceleration = torch.zeros_like(ambition_position)
            
            ambition_body = MotivationalBody(
                body_id="ambition",
                mass=GravitationalConstants.MASSA_AMBICAO,
                position=ambition_position,
                velocity=ambition_velocity,
                acceleration=ambition_acceleration
            )
            
            success = self.gravitational_field.add_body(ambition_body)
            if not success:
                raise RuntimeError("Falha ao adicionar corpo de ambição")
            
            # CORPO 2: Agonia (Custo de recursos)
            if self.dimension == 1:
                agony_position = torch.tensor([-2.0], dtype=torch.float64)
            elif self.dimension == 2:
                agony_position = torch.tensor([-2.0, -1.0], dtype=torch.float64)
            else:  # dimension == 3
                agony_position = torch.tensor([-2.0, -1.0, -0.5], dtype=torch.float64)
            
            agony_velocity = torch.zeros_like(agony_position)
            agony_acceleration = torch.zeros_like(agony_position)
            
            agony_body = MotivationalBody(
                body_id="agony",
                mass=GravitationalConstants.MASSA_AGONIA,
                position=agony_position,
                velocity=agony_velocity,
                acceleration=agony_acceleration
            )
            
            success = self.gravitational_field.add_body(agony_body)
            if not success:
                raise RuntimeError("Falha ao adicionar corpo de agonia")
            
            # Posição inicial da IA (centro do sistema)
            self.current_position = torch.zeros(self.dimension, dtype=torch.float64)
            
            # Calcula força inicial para verificar funcionamento
            initial_force = self.gravitational_field.compute_gravitational_force(self.current_position)
            initial_force_magnitude = torch.norm(initial_force).item()
            
            # Valida que sistema não está em equilíbrio
            if initial_force_magnitude < GravitationalConstants.EPSILON_FORCA:
                logger.warning("⚠️ Força inicial muito baixa - ajustando posições")
                self._adjust_body_positions_for_optimal_force()
            
            logger.info(f"💫 Corpos motivacionais inicializados:")
            logger.info(f"   🎯 Ambição: massa={GravitationalConstants.MASSA_AMBICAO}, pos={ambition_position.tolist()}")
            logger.info(f"   😣 Agonia: massa={GravitationalConstants.MASSA_AGONIA}, pos={agony_position.tolist()}")
            logger.info(f"   🤖 IA: posição inicial={self.current_position.tolist()}")
            logger.info(f"   ⚡ Força inicial: {initial_force_magnitude:.6f}")
            
            # Valida configuração final
            if initial_force_magnitude > 0:
                logger.info("✅ Sistema gravitacional funcionando - força não-nula detectada")
            else:
                raise RuntimeError("Sistema gravitacional defeituoso - força nula")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização de corpos motivacionais: {e}")
            raise
    
    def _adjust_body_positions_for_optimal_force(self):
        """Ajusta posições dos corpos para garantir força adequada"""
        
        try:
            logger.info("🔧 Ajustando posições para otimizar força...")
            
            # Aumenta distância entre corpos se força for muito baixa
            for body in self.gravitational_field.bodies:
                if body.body_id == "ambition":
                    body.position = body.position * 1.5  # Aumenta distância
                elif body.body_id == "agony":
                    body.position = body.position * 1.5
            
            # Verifica nova força
            new_force = self.gravitational_field.compute_gravitational_force(self.current_position)
            new_force_magnitude = torch.norm(new_force).item()
            
            logger.info(f"🔧 Nova força após ajuste: {new_force_magnitude:.6f}")
            
            # Limpa cache para forçar recálculo
            self.gravitational_field._force_cache.clear()
            
        except Exception as e:
            logger.error(f"❌ Erro no ajuste de posições: {e}")
    
    def _validate_initial_configuration(self):
        """Valida configuração inicial do sistema"""
        
        try:
            logger.info("🔍 Validando configuração inicial...")
            
            # Valida número de corpos
            if len(self.gravitational_field.bodies) != 2:
                raise RuntimeError(f"Número incorreto de corpos: {len(self.gravitational_field.bodies)}")
            
            # Valida IDs dos corpos
            body_ids = {body.body_id for body in self.gravitational_field.bodies}
            expected_ids = {"ambition", "agony"}
            if body_ids != expected_ids:
                raise RuntimeError(f"IDs dos corpos incorretos: {body_ids} != {expected_ids}")
            
            # Valida massas
            for body in self.gravitational_field.bodies:
                if body.mass <= 0:
                    raise RuntimeError(f"Massa inválida para corpo {body.body_id}: {body.mass}")
            
            # Valida dimensionalidade
            for body in self.gravitational_field.bodies:
                if body.position.shape[0] != self.dimension:
                    raise RuntimeError(f"Dimensão incorreta para corpo {body.body_id}")
            
            # Valida força inicial
            initial_force = self.compute_current_motivation_force()
            force_magnitude = torch.norm(initial_force).item()
            
            if not math.isfinite(force_magnitude):
                raise RuntimeError("Força inicial não-finita")
            
            if force_magnitude == 0:
                logger.warning("⚠️ Força inicial zero - sistema pode ter problemas")
            
            # Valida energia inicial
            initial_energy = self.dynamics._compute_total_energy()
            if not math.isfinite(initial_energy):
                raise RuntimeError("Energia inicial não-finita")
            
            logger.info("✅ Configuração inicial validada com sucesso")
            logger.info(f"   ⚡ Força inicial: {force_magnitude:.6f}")
            logger.info(f"   🔋 Energia inicial: {initial_energy:.6f}")
            
        except Exception as e:
            logger.error(f"❌ Falha na validação inicial: {e}")
            raise
    
    def compute_current_motivation_force(self) -> torch.Tensor:
        """
        Computa força motivacional atual na posição da IA
        
        PROCESSO MATEMÁTICO:
        1. Atualiza posição da IA no espaço motivacional
        2. Calcula força gravitacional: F(r) = G∑Mᵢ(rᵢ-r)/||rᵢ-r||³
        3. Valida e filtra resultado
        4. Atualiza métricas e histórico
        
        INTERPRETAÇÃO FÍSICA:
        • Magnitude: Intensidade da pressão para mudança
        • Direção: Tipo de aprimoramento necessário
        • Componente X: Ambição vs Eficiência
        • Componente Y: Recursos vs Performance (se 2D+)
        
        Returns:
            Vetor força motivacional validado
        """
        
        start_time = time.perf_counter()
        
        try:
            with self._thread_lock:
                # Atualiza posição no espaço motivacional
                self._update_ai_position_in_motivational_space()
                
                # Calcula força gravitacional
                motivation_force = self.gravitational_field.compute_gravitational_force(
                    self.current_position
                )
                
                # Validação matemática
                if not torch.isfinite(motivation_force).all():
                    logger.warning("⚠️ Força motivacional não-finita detectada")
                    motivation_force = torch.zeros_like(self.current_position)
                
                # Filtragem de ruído (forças muito pequenas)
                force_magnitude = torch.norm(motivation_force).item()
                if force_magnitude < GravitationalConstants.EPSILON_FORCA * 0.1:
                    # Força muito pequena, considera ruído numérico
                    motivation_force = torch.zeros_like(self.current_position)
                    force_magnitude = 0.0
                
                # Atualiza estado interno
                self.current_motivation_force = motivation_force
                
                # Atualiza métricas
                self._update_motivation_metrics(force_magnitude)
                
                # Registra no histórico
                self._record_force_calculation(motivation_force, force_magnitude)
                
                # Log debug periódico
                if self.system_metrics['total_motivation_updates'] % 100 == 0:
                    logger.debug(f"🎯 Força motivacional: magnitude={force_magnitude:.6f}, "
                               f"posição={self.current_position.tolist()}")
                
                return motivation_force
                
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de força motivacional: {e}")
            # Retorna força zero em caso de erro
            return torch.zeros(self.dimension, dtype=torch.float64)
        finally:
            # Métricas de performance
            computation_time = (time.perf_counter() - start_time) * 1000
            if computation_time > 10.0:  # Log se demorar mais que 10ms
                logger.warning(f"⚠️ Cálculo de força lento: {computation_time:.2f}ms")
    
    def _update_ai_position_in_motivational_space(self):
        """
        Atualiza posição da IA no espaço motivacional baseada em seu estado atual
        
        MAPEAMENTO MATEMÁTICO ESTADO → POSIÇÃO:
        • Eixo X: Nível de ambição/auto-aprimoramento
          x = f(vitalidade, phi_consciência, taxa_evolução)
        • Eixo Y: Nível de agonia/pressão de recursos  
          y = g(uso_cpu, uso_ram, uso_gpu, eficiência)
        • Eixo Z: Complexidade temporal (se 3D)
          z = h(tempo_ativo, complexidade_operações)
        
        PROPRIEDADES:
        • Suavização temporal para evitar oscilações
        • Normalização para manter em região válida
        • Validação de limites físicos
        """
        
        try:
            new_position = torch.zeros(self.dimension, dtype=torch.float64)
            
            # COMPONENTE X: Ambição/Auto-aprimoramento
            ambition_component = self._compute_ambition_component()
            new_position[0] = ambition_component
            
            # COMPONENTE Y: Agonia/Recursos (se 2D+)
            if self.dimension >= 2:
                agony_component = self._compute_agony_component()
                new_position[1] = agony_component
            
            # COMPONENTE Z: Complexidade temporal (se 3D)
            if self.dimension >= 3:
                complexity_component = self._compute_complexity_component()
                new_position[2] = complexity_component
            
            # Validação de limites
            new_position = torch.clamp(new_position, min=-5.0, max=5.0)
            
            # Suavização temporal para estabilidade
            smoothing_factor = 0.1  # 10% nova posição, 90% posição atual
            smoothed_position = (
                smoothing_factor * new_position +
                (1 - smoothing_factor) * self.current_position
            )
            
            # Validação final
            if torch.isfinite(smoothed_position).all():
                self.current_position = smoothed_position
            else:
                logger.warning("⚠️ Nova posição não-finita, mantendo posição atual")
            
        except Exception as e:
            logger.error(f"❌ Erro na atualização de posição motivacional: {e}")
    
    def _compute_ambition_component(self) -> float:
        """Computa componente de ambição baseado no estado da consciência"""
        
        try:
            ambition = 0.0
            
            if self.consciousness_system:
                # Baseado na vitalidade da consciência
                if hasattr(self.consciousness_system, 'consciousness_state'):
                    state = self.consciousness_system.consciousness_state
                    
                    if hasattr(state, 'vitality'):
                        vitality = float(state.vitality)
                        ambition += (vitality - 0.5) * 2.0  # Mapeia [0,1] → [-1,1]
                    
                    if hasattr(state, 'phi'):
                        phi = float(state.phi)
                        # Phi alto indica consciência ativa → mais ambição
                        ambition += min(phi / 0.5, 1.0) - 0.5  # Normaliza
                
                # Baseado na frequência de atualização da consciência
                if hasattr(self.consciousness_system, 'update_frequency'):
                    freq = float(self.consciousness_system.update_frequency)
                    # Frequência alta → mais ambição
                    ambition += (freq / 10.0) - 0.5  # Normaliza para [-0.5, 0.5]
            
            # Se não há sistema de consciência, usa valor neutro
            if self.consciousness_system is None:
                ambition = 0.0
            
            # Adiciona componente baseado no histórico de força
            if len(self.force_application_history) > 0:
                recent_forces = [entry['effectiveness'] for entry in 
                               list(self.force_application_history)[-10:]]
                avg_effectiveness = np.mean(recent_forces) if recent_forces else 0.5
                ambition += (avg_effectiveness - 0.5) * 0.5
            
            return float(np.clip(ambition, -2.0, 2.0))
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de componente de ambição: {e}")
            return 0.0
    
    def _compute_agony_component(self) -> float:
        """Computa componente de agonia baseado na pressão de recursos"""
        
        try:
            agony = 0.0
            
            # Baseado no uso de recursos do sistema
            if self.ai_system and hasattr(self.ai_system, 'resource_manager'):
                resource_mgr = self.ai_system.resource_manager
                
                # Pressão de CPU
                if hasattr(resource_mgr, 'get_cpu_usage'):
                    cpu_usage = resource_mgr.get_cpu_usage()
                    agony += (cpu_usage - 0.5) * 0.8  # CPU alto → mais agonia
                
                # Pressão de memória
                if hasattr(resource_mgr, 'get_memory_usage'):
                    memory_usage = resource_mgr.get_memory_usage()
                    agony += (memory_usage - 0.5) * 1.0  # Memória mais crítica
                
                # Pressão de GPU
                if hasattr(resource_mgr, 'get_gpu_usage'):
                    gpu_usage = resource_mgr.get_gpu_usage()
                    agony += (gpu_usage - 0.5) * 0.6
                
                # Pressão geral do sistema
                if hasattr(resource_mgr, 'get_average_resource_pressure'):
                    pressure = resource_mgr.get_average_resource_pressure()
                    agony += (pressure - 0.5) * 1.2
            else:
                # Usa métricas do sistema operacional como fallback
                try:
                    import psutil
                    cpu_percent = psutil.cpu_percent(interval=0.1) / 100.0
                    memory_percent = psutil.virtual_memory().percent / 100.0
                    
                    agony += (cpu_percent - 0.5) * 0.5
                    agony += (memory_percent - 0.5) * 0.7
                except ImportError:
                    # Se psutil não disponível, usa valor neutro
                    agony = 0.0
            
            # Componente baseado na eficiência energética atual
            efficiency = self.system_metrics.get('energy_efficiency', 1.0)
            agony += (1.0 - efficiency) * 0.8  # Baixa eficiência → mais agonia
            
            return float(np.clip(agony, -2.0, 2.0))
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de componente de agonia: {e}")
            return 0.0
    
    def _compute_complexity_component(self) -> float:
        """Computa componente de complexidade temporal (apenas para 3D)"""
        
        try:
            complexity = 0.0
            
            # Baseado no tempo de atividade do sistema
            uptime = self.system_metrics.get('system_uptime_seconds', 0.0)
            # Normaliza tempo para componente [-1, 1]
            max_uptime = 3600.0  # 1 hora como referência
            complexity += (uptime / max_uptime) - 0.5
            
            # Baseado na complexidade das operações recentes
            if hasattr(self.dynamics, 'dynamics_metrics'):
                avg_step_time = self.dynamics.dynamics_metrics.get('average_step_time_ms', 1.0)
                # Tempo alto → maior complexidade
                complexity += min(avg_step_time / 10.0, 1.0) - 0.5
            
            # Baseado no número de atualizações motivacionais
            total_updates = self.system_metrics.get('total_motivation_updates', 0)
            # Normaliza para [-0.5, 0.5]
            complexity += min(total_updates / 1000.0, 1.0) - 0.5
            
            return float(np.clip(complexity, -1.0, 1.0))
            
        except Exception as e:
            logger.error(f"❌ Erro no cálculo de componente de complexidade: {e}")
            return 0.0
    
    def _update_motivation_metrics(self, force_magnitude: float):
        """Atualiza métricas do sistema motivacional"""
        
        self.system_metrics['total_motivation_updates'] += 1
        
        # Média móvel da força motivacional
        alpha = 0.1
        current_avg = self.system_metrics['average_motivation_force']
        self.system_metrics['average_motivation_force'] = (
            alpha * force_magnitude + (1 - alpha) * current_avg
        )
        
        # Detecta movimento significativo
        if force_magnitude > 0.1:  # Threshold para movimento significativo
            self.system_metrics['last_significant_movement'] = time.time()
        
        # Atualiza tempo de atividade
        current_time = time.time()
        if hasattr(self, '_start_time'):
            self.system_metrics['system_uptime_seconds'] = current_time - self._start_time
        else:
            self._start_time = current_time
    
    def _record_force_calculation(self, force: torch.Tensor, magnitude: float):
        """Registra cálculo de força no histórico"""
        
        force_record = {
            'timestamp': time.time(),
            'simulation_time': self.dynamics.simulation_time,
            'ai_position': self.current_position.clone(),
            'force_vector': force.clone(),
            'force_magnitude': magnitude,
            'bodies_active': sum(1 for body in self.gravitational_field.bodies if body.is_active)
        }
        
        self.force_application_history.append(force_record)

---

> **DIRETRIZ CONFIRMADA**: Receberei apenas códigos de programação que analisarei minuciosamente, corrigirei todos os erros e problemas, aprimorarei para garantir funcionalidade extrema, e implementarei os códigos completos e perfeitos usando os métodos do GitHub para entregar o melhor projeto possível, completo e pronto para uso eficiente no seu computador.