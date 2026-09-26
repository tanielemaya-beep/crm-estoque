from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuração do Banco de Dados (funciona local e no servidor)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'sqlite:///estoque_financeiro.db'
)
app.config['SECRET_KEY'] = 'sua_chave_secreta_super_segura'
db = SQLAlchemy(app)


# --- MODELOS DE DADOS ---
class Produto(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  nome = db.Column(db.String(100), nullable=False)
  preco_custo = db.Column(db.Float, nullable=False)
  preco_venda = db.Column(db.Float, nullable=False)
  estoque = db.Column(db.Integer, nullable=False)


class Venda(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  produto_id = db.Column(
      db.Integer, db.ForeignKey('produto.id'), nullable=False
  )
  quantidade = db.Column(db.Integer, nullable=False)
  valor_total = db.Column(db.Float, nullable=False)
  data = db.Column(db.DateTime, default=datetime.utcnow)
  produto = db.relationship('Produto', backref=db.backref('vendas', lazy=True))


class ContaPagar(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  descricao = db.Column(db.String(200), nullable=False)
  valor = db.Column(db.Float, nullable=False)
  data_vencimento = db.Column(db.String(10), nullable=False)
  status = db.Column(db.String(20), default='Pendente')


with app.app_context():
  db.create_all()


# --- ROTAS PRINCIPAIS ---
@app.route('/')
def dashboard():
  produtos_criticos = Produto.query.filter(Produto.estoque <= 5).all()
  total_vendas = db.session.query(db.func.sum(Venda.valor_total)).scalar() or 0

  total_a_pagar = (
      db.session.query(db.func.sum(ContaPagar.valor))
      .filter_by(status='Pendente')
      .scalar()
      or 0
  )
  total_pago = (
      db.session.query(db.func.sum(ContaPagar.valor))
      .filter_by(status='Pago')
      .scalar()
      or 0
  )

  return render_template(
      'dashboard.html',
      total_vendas=total_vendas,
      total_a_pagar=total_a_pagar,
      total_pago=total_pago,
      produtos_criticos=produtos_criticos,
  )


@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
  if request.method == 'POST':
    try:
      nome = request.form['nome']
      preco_custo = float(request.form['preco_custo'])
      preco_venda = float(request.form['preco_venda'])
      estoque = int(request.form['estoque'])

      novo_produto = Produto(
          nome=nome,
          preco_custo=preco_custo,
          preco_venda=preco_venda,
          estoque=estoque,
      )
      db.session.add(novo_produto)
      db.session.commit()
      flash('Produto cadastrado com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro ao cadastrar produto: {str(e)}')
    return redirect(url_for('produtos'))

  lista_produtos = Produto.query.all()
  return render_template('produtos.html', produtos=lista_produtos)


@app.route('/vendas', methods=['GET', 'POST'])
def vendas():
  if request.method == 'POST':
    try:
      produto_id = int(request.form['produto_id'])
      quantidade = int(request.form['quantidade'])

      produto = Produto.query.get_or_404(produto_id)

      if produto.estoque < quantidade:
        flash('Erro: Quantidade solicitada indisponível em stock!')
        return redirect(url_for('vendas'))

      valor_total = produto.preco_venda * quantidade
      produto.estoque -= quantidade

      nova_venda = Venda(
          produto_id=produto_id, quantidade=quantidade, valor_total=valor_total
      )
      db.session.add(nova_venda)
      db.session.commit()

      flash('Venda registada e stock atualizado com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro ao processar venda: {str(e)}')

    return redirect(url_for('vendas'))

  lista_produtos = Produto.query.all()
  historico_vendas = Venda.query.order_by(Venda.data.desc()).all()
  return render_template(
      'vendas.html', produtos=lista_produtos, vendas=historico_vendas
  )


@app.route('/contas-pagar', methods=['GET', 'POST'])
def contas_pagar():
  if request.method == 'POST':
    try:
      descricao = request.form['descricao']
      valor = float(request.form['valor'])
      data_vencimento = request.form['data_vencimento']

      nova_conta = ContaPagar(
          descricao=descricao,
          valor=valor,
          data_vencimento=data_vencimento,
          status='Pendente',
      )
      db.session.add(nova_conta)
      db.session.commit()
      flash('Conta a pagar cadastrada com sucesso!')
    except Exception as e:
      db.session.rollback()
      flash(f'Erro ao cadastrar conta: {str(e)}')
    return redirect(url_for('contas_pagar'))

  contas = ContaPagar.query.order_by(ContaPagar.data_vencimento).all()
  return render_template('contas_pagar.html', contas=contas)


@app.route('/pagar-conta/<int:id>')
def pagar_conta(id):
  try:
    conta = ContaPagar.query.get_or_404(id)
    conta.status = 'Pago'
    db.session.commit()
    flash('Conta marcada como paga!')
  except Exception as e:
    db.session.rollback()
    flash(f'Erro ao pagar conta: {str(e)}')
  return redirect(url_for('contas_pagar'))


if __name__ == '__main__':
  app.run(debug=True)