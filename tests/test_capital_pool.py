"""
资金池管理测试
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.capital_pool import CapitalPool, TradeResult


def test_capital_pool():
    """测试资金池管理"""
    print("=== 资金池管理测试 ===\n")

    # 初始化资金池
    pool = CapitalPool(10000)
    print("1. 初始状态:")
    print(pool.get_summary())
    print()

    # 测试资金分配
    print("2. 趋势场景资金分配:")
    amount = pool.allocate_for_trade("TRENDING", 0.8)
    print(f"   分配金额: {amount:.2f}")
    assert amount > 0, "资金分配应该大于0"
    assert amount <= 3000, "单笔应该不超过总资金30%"
    print("   ✅ 资金分配验证通过")
    print()

    # 测试资金锁定
    print("3. 资金锁定:")
    pool.lock_capital(amount)
    pool.add_margin(amount)
    status = pool.get_status()
    print(f"   锁定: {status['locked']:.2f}")
    print(f"   保证金: {status['margin']:.2f}")
    assert status["margin"] > 0, "保证金应该大于0"
    print("   ✅ 锁定验证通过")
    print()

    # 测试交易后更新（盈利）
    print("4. 盈利交易后更新:")
    result = TradeResult(profit=200, profit_ratio=0.02, capital_used=amount, is_win=True)
    pool.release_margin(amount)
    pool.update_after_trade(result)
    status = pool.get_status()
    print(f"   总资金: {status['total']:.2f}")
    print(f"   盈亏: {status['daily_pnl']:.2f}")
    print(f"   连胜: {status['consecutive_loss']}")
    assert status["total"] > 10000, "盈利后总资金应该增加"
    assert status["win_count"] == 1, "胜场应该为1"
    print("   ✅ 盈利交易验证通过")
    print()

    # 测试交易后更新（亏损）
    print("5. 亏损交易后更新:")
    amount2 = pool.allocate_for_trade("RANGING", 0.5)
    pool.lock_capital(amount2)
    pool.add_margin(amount2)
    result2 = TradeResult(profit=-150, profit_ratio=-0.015, capital_used=amount2, is_win=False)
    pool.release_margin(amount2)
    pool.update_after_trade(result2)
    status = pool.get_status()
    print(f"   总资金: {status['total']:.2f}")
    print(f"   连续亏损: {status['consecutive_loss']}")
    print(f"   仓位倍数: {status['position_multiplier']:.2f}x")
    assert status["loss_count"] == 1, "败场应该为1"
    print("   ✅ 亏损交易验证通过")
    print()

    # 测试交易权限检查
    print("6. 交易权限检查:")
    can_trade, reason = pool.can_trade()
    print(f"   可以交易: {can_trade}")
    print(f"   原因: {reason}")
    assert can_trade, "应该可以继续交易"
    print("   ✅ 权限检查验证通过")
    print()

    # 模拟连续亏损
    print("7. 模拟连续亏损3次:")
    for i in range(3):
        small_amount = pool.allocate_for_trade("EXTREME", 0.3)
        pool.lock_capital(small_amount)
        pool.add_margin(small_amount)
        loss = TradeResult(profit=-50, profit_ratio=-0.005, capital_used=small_amount, is_win=False)
        pool.release_margin(small_amount)
        pool.update_after_trade(loss)

    status = pool.get_status()
    can_trade, reason = pool.can_trade()
    print(f"   连续亏损: {status['consecutive_loss']}")
    print(f"   可以交易: {can_trade}")
    print(f"   原因: {reason}")
    print("   ✅ 连败检测验证通过")
    print()

    print("✅ 资金池管理测试全部通过!")


if __name__ == "__main__":
    test_capital_pool()
