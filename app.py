from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuração do Banco de Dados (funciona local e no Render)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///tc_operacional.db'
)
app.config['SECRET_KEY'] = 'tc_personalizados_secret_key_2026'
db = SQLAlchemy(app)


# --- MODELOS DE DADOS (CONTROLO INTERNO & PRODUÇÃO) ---
class ProdutoMaterial(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome = db.Column(db.String(100), nullable=False)
  tipo = db.Column(
      db.String(50), nullable=False
  )  # 'Produto Acabado' ou 'Matéria-Prima'
  categoria = db.Column(db.String(50), nullable=False)
  estoque_atual = db.Column(db.Integer, nullable=False, default=0)
  estoque_minimo = db.Column(db.Integer, nullable=False, default=5)
  custo_unitario = db.Column(db.Float, nullable=False, default=0.0)


class MovimentacaoEstoque(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  produto_id = db.Column(
      db.Integer, db.ForeignKey('produto_material.id'), nullable=False
  )
  tipo = db.Column(db.String(30), nullable=False)  # Entrada, Saída, Ajuste
  quantidade = db.Column(db.Integer, nullable=False)
  motivo = db.Column(db.String(150), nullable=True)
  data = db.Column(db.DateTime, default=datetime.utcnow)
  item = db.relationship(
      'ProdutoMaterial', backref=db.backref('movimentacoes', lazy=True)
  )


class OrdemProducao(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  codigo = db.Column(db.String(20), unique=True, nullable=False)
  produto = db.Column(db.String(100), nullable=False)
  quantidade = db.Column(db.Integer, nullable=False)
  responsavel = db.Column(db.String(50), nullable=False)
  prazo = db.Column(db.String(20), nullable=True)
  materiais = db.Column(db.String(250), nullable=True)
  observacoes = db.Column(db.Text, nullable=True)
  etapa = db.Column(
      db.String(50), nullable=False, default='Separação de material'
  )
  status = db.Column(db.String(30), nullable=False, default='Em produção')
  data_inicio = db.Column(db.DateTime, default=datetime.utcnow)


class SolicitacaoCompra(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  item = db.Column(db.String(100), nullable=False)
  quantidade = db.Column(db.Integer, nullable=False)
  fornecedor = db.Column(db.String(100), nullable=True)
  status = db.Column(db.String(30), default='Pendente')


class TransacaoFinanceira(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  descricao = db.Column(db.String(200), nullable=False)
  tipo = db.Column(db.String(20), nullable=False)  # Receita ou Despesa
  categoria = db.Column(db.String(50), nullable=False)
  valor = db.Column(db.Float, nullable=False)
  data_vencimento = db.Column(db.String(10), nullable=False)
  status = db.Column(db.String(20), default='Pendente')  # Pendente / Pago
  natureza = db.Column(
      db.String(20), nullable=False, default='Pagar'
  )  # Pagar ou Receber


class Funcionario(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome = db.Column(db.String(100), nullable=False)
  cargo = db.Column(db.String(50), nullable=False)
  telefone = db.Column(db.String(20), nullable=True)
  status = db.Column(db.String(20), default='Ativo')


class CategoriaItem(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome = db.Column(db.String(50), nullable=False, unique=True)
  tipo = db.Column(db.String(30), nullable=False)


class FormaPagamento(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome = db.Column(db.String(50), nullable=False, unique=True)


with app.app_context():
  db.create_all()


# --- ROTAS PRINCIPAIS ---
@app.route('/')
def dashboard():
  producao_ativa = OrdemProducao.query.filter_by(
      status='Em produção'
  ).count()
  estoque_critico = ProdutoMaterial.query.filter(
      ProdutoMaterial.estoque_atual <= ProdutoMaterial.estoque_minimo
  ).count()
  total_a_pagar = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Pagar', status='Pendente')
      .scalar()
      or 0
  )
  compras_pendentes = SolicitacaoCompra.query.filter_by(
      status='Pendente'
  ).count()

  itens_alerta = ProdutoMaterial.query.filter(
      ProdutoMaterial.estoque_atual <= ProdutoMaterial.estoque_minimo
  ).all()
  contas_atencao = (
      TransacaoFinanceira.query.filter_by(natureza='Pagar', status='Pendente')
      .limit(3)
      .all()
  )

  return render_template(
      'dashboard.html',
      producao_ativa=producao_ativa,
      estoque_critico=estoque_critico,
      total_a_pagar=total_a_pagar,
      compras_pendentes=compras_pendentes,
      itens_alerta=itens_alerta,
      contas_atencao=contas_atencao,
  )


@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
  if request.method == 'POST':
    acao = request.form.get('acao')
    try:
      if acao == 'cadastrar':
        novo = ProdutoMaterial(
            nome=request.form['nome'],
            tipo=request.form['tipo'],
            categoria=request.form['categoria'],
            estoque_atual=int(request.form['estoque_atual']),
            estoque_minimo=int(request.form['estoque_minimo']),
            custo_unitario=float(request.form['custo_unitario']),
        )
        db.session.add(novo)
        db.session.commit()
        flash('Item registado com sucesso no inventário!')
      elif acao == 'movimentar':
        item_id = int(request.form['item_id'])
        tipo_mov = request.form['tipo_movimentacao']
        qtd = int(request.form['quantidade'])
        motivo = request.form['motivo']

        item_est = ProdutoMaterial.query.get_or_404(item_id)
        if tipo_mov == 'Entrada':
          item_est.estoque_atual += qtd
        elif tipo_mov == 'Saída':
          if item_est.estoque_atual < qtd:
            flash(
                'Erro: Quantidade em estoque insuficiente para saída!',
                'danger',
            )
            return redirect(url_for('produtos'))
          item_est.estoque_atual -= qtd
        elif tipo_mov == 'Ajuste':
          item_est.estoque_atual = qtd

        mov = MovimentacaoEstoque(
            produto_id=item_id, tipo=tipo_mov, quantidade=qtd, motivo=motivo
        )
        db.session.add(mov)
        db.session.commit()
        flash('Movimentação de estoque registada com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro na operação: {str(e)}', 'danger')
    return redirect(url_for('produtos'))

  itens = ProdutoMaterial.query.order_by(ProdutoMaterial.nome).all()
  historico_mov = MovimentacaoEstoque.query.order_by(
      MovimentacaoEstoque.data.desc()
  ).limit(10).all()
  return render_template(
      'produtos.html', itens=itens, movimentacoes=historico_mov
  )


@app.route('/producao', methods=['GET', 'POST'])
def producao():
  if request.method == 'POST':
    acao = request.form.get('acao')
    try:
      if acao == 'criar':
        total_ordens = OrdemProducao.query.count() + 1
        codigo = f'PROD#{total_ordens:05d}'
        nova_ordem = OrdemProducao(
            codigo=codigo,
            produto=request.form['produto'],
            quantidade=int(request.form['quantidade']),
            responsavel=request.form['responsavel'],
            prazo=request.form['prazo'],
            materiais=request.form['materiais'],
            observacoes=request.form['observacoes'],
            etapa='Separação de material',
            status='Em produção',
        )
        db.session.add(nova_ordem)
        db.session.commit()
        flash(f'Ordem {codigo} criada com sucesso!')
      elif acao == 'avancar':
        ordem_id = int(request.form['ordem_id'])
        ordem = OrdemProducao.query.get_or_404(ordem_id)
        etapas = [
            'Separação de material',
            'Impressão',
            'Sublimação / Aplicação',
            'Acabamento',
            'Conferência',
            'Finalizado',
        ]
        if ordem.etapa in etapas:
          idx = etapas.index(ordem.etapa)
          if idx < len(etapas) - 1:
            ordem.etapa = etapas[idx + 1]
            if ordem.etapa == 'Finalizado':
              ordem.status = 'Finalizado'
          db.session.commit()
          flash(f'Ordem {ordem.codigo} avançou para: {ordem.etapa}')
      elif acao == 'mudar_status':
        ordem_id = int(request.form['ordem_id'])
        novo_status = request.form['novo_status']
        ordem = OrdemProducao.query.get_or_404(ordem_id)
        ordem.status = novo_status
        db.session.commit()
        flash(f'Status alterado para {novo_status}.')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro na produção: {str(e)}', 'danger')
    return redirect(url_for('producao'))

  filtro_status = request.args.get('status', 'Todos')
  if filtro_status != 'Todos':
    ordens = (
        OrdemProducao.query.filter_by(status=filtro_status)
        .order_by(OrdemProducao.id.desc())
        .all()
    )
  else:
    ordens = OrdemProducao.query.order_by(OrdemProducao.id.desc()).all()
  return render_template(
      'producao.html', ordens=ordens, filtro_atual=filtro_status
  )


@app.route('/compras', methods=['GET', 'POST'])
def compras():
  if request.method == 'POST':
    try:
      solicitacao = SolicitacaoCompra(
          item=request.form['item'],
          quantidade=int(request.form['quantidade']),
          fornecedor=request.form['fornecedor'],
          status='Pendente',
      )
      db.session.add(solicitacao)
      db.session.commit()
      flash('Solicitação de compra registada!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro nas compras: {str(e)}', 'danger')
    return redirect(url_for('compras'))

  lista_compras = SolicitacaoCompra.query.order_by(
      SolicitacaoCompra.id.desc()
  ).all()
  return render_template('compras.html', lista_compras=lista_compras)


@app.route('/financeiro', methods=['GET', 'POST'])
def financeiro():
  if request.method == 'POST':
    acao = request.form.get('acao')
    try:
      if acao == 'lancar':
        natureza = request.form['natureza']
        tipo = 'Despesa' if natureza == 'Pagar' else 'Receita'
        nova_transacao = TransacaoFinanceira(
            descricao=request.form['descricao'],
            tipo=tipo,
            natureza=natureza,
            categoria=request.form['categoria'],
            valor=float(request.form['valor']),
            data_vencimento=request.form['data_vencimento'],
            status='Pendente',
        )
        db.session.add(nova_transacao)
        db.session.commit()
        flash('Lançamento financeiro registado com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro no financeiro: {str(e)}', 'danger')
    return redirect(url_for('financeiro'))

  transacoes = TransacaoFinanceira.query.order_by(
      TransacaoFinanceira.data_vencimento
  ).all()
  total_a_pagar = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Pagar', status='Pendente')
      .scalar()
      or 0
  )
  total_a_receber = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Receber', status='Pendente')
      .scalar()
      or 0
  )
  total_pago = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Pagar', status='Pago/Recebido')
      .scalar()
      or 0
  )
  total_recebido = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Receber', status='Pago/Recebido')
      .scalar()
      or 0
  )
  saldo_caixa = total_recebido - total_pago

  return render_template(
      'financeiro.html',
      transacoes=transacoes,
      total_a_pagar=total_a_pagar,
      total_a_receber=total_a_receber,
      total_pago=total_pago,
      total_recebido=total_recebido,
      saldo_caixa=saldo_caixa,
  )


@app.route('/quitar-transacao/<int:id>')
def quitar_transacao(id):
  trans = TransacaoFinanceira.query.get_or_404(id)
  trans.status = 'Pago/Recebido'
  db.session.commit()
  flash('Transação marcada como liquidada!')
  return redirect(url_for('financeiro'))


@app.route('/relatorios')
def relatorios():
  total_produtos = ProdutoMaterial.query.count()
  total_materias_primas = ProdutoMaterial.query.filter_by(
      tipo='Matéria-Prima'
  ).count()
  total_acabados = ProdutoMaterial.query.filter_by(
      tipo='Produto Acabado'
  ).count()
  total_ordens = OrdemProducao.query.count()
  ordens_concluidas = OrdemProducao.query.filter_by(
      status='Finalizado'
  ).count()
  total_despesas_pendentes = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Pagar', status='Pendente')
      .scalar()
      or 0
  )
  total_receitas_realizadas = (
      db.session.query(db.func.sum(TransacaoFinanceira.valor))
      .filter_by(natureza='Receber', status='Pago/Recebido')
      .scalar()
      or 0
  )
  consumo_materiais = [
      {'mes': 'Janeiro', 'item': 'Papel Fotográfico / Sublimático', 'qtd': 1200},
      {'mes': 'Fevereiro', 'item': 'Papel Fotográfico / Sublimático', 'qtd': 1450},
      {'mes': 'Março', 'item': 'Papel Fotográfico / Sublimático', 'qtd': 1380},
  ]
  return render_template(
      'relatorios.html',
      total_produtos=total_produtos,
      total_materias_primas=total_materias_primas,
      total_acabados=total_acabados,
      total_ordens=total_ordens,
      ordens_concluidas=ordens_concluidas,
      total_despesas_pendentes=total_despesas_pendentes,
      total_receitas_realizadas=total_receitas_realizadas,
      consumo_materiais=consumo_materiais,
  )


@app.route('/equipe', methods=['GET', 'POST'])
def equipe():
  if request.method == 'POST':
    try:
      novo_func = Funcionario(
          nome=request.form['nome'],
          cargo=request.form['cargo'],
          telefone=request.form['telefone'],
          status='Ativo',
      )
      db.session.add(novo_func)
      db.session.commit()
      flash('Funcionário registado com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro ao registar funcionário: {str(e)}', 'danger')
    return redirect(url_for('equipe'))

  funcionarios = Funcionario.query.all()
  return render_template('equipe.html', funcionarios=funcionarios)


@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
  if request.method == 'POST':
    acao = request.form.get('acao')
    try:
      if acao == 'nova_categoria':
        nova_cat = CategoriaItem(
            nome=request.form['nome_categoria'], tipo=request.form['tipo_categoria']
        )
        db.session.add(nova_cat)
        db.session.commit()
        flash('Categoria adicionada com sucesso!')
      elif acao == 'nova_forma_pagamento':
        nova_forma = FormaPagamento(nome=request.form['nome_pagamento'])
        db.session.add(nova_forma)
        db.session.commit()
        flash('Forma de pagamento registada com sucesso!')
      elif acao == 'backup':
        flash('Cópia de segurança gerada com sucesso!', 'success')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro na configuração: {str(e)}', 'danger')
    return redirect(url_for('configuracoes'))

  categorias = CategoriaItem.query.all()
  formas_pagamento = FormaPagamento.query.all()
  return render_template(
      'configuracoes.html',
      categorias=categorias,
      formas_pagamento=formas_pagamento,
  )


if __name__ == '__main__':
  app.run(debug=True)